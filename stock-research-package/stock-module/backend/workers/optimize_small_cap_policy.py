"""Read-only, training-selected small-cap refinements with retrospective time validation."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, UTC
from hashlib import sha256
import json
import math
from pathlib import Path
import random

from app.domain.market_lines import MarketLineSnapshot
from app.domain.small_cap_backtest import TradePolicy
from app.domain.strategies import StockSeries
from workers.backtest_small_cap_policy import (
    collect_signals, run_cohort, summarize_trades, _write_csv, cohort_signal_eligible, validate_cohort_options,
)


@dataclass(frozen=True)
class Trial:
    id: str
    dip_pct: float = .01
    ordinary_only: bool = False
    max_drawdown_pct: float | None = None
    max_contraction: float | None = None
    max_probe_age: int | None = None
    max_probe_volume: float | None = None
    min_confirmation_volume: float | None = None

    def policy(self) -> TradePolicy:
        return TradePolicy(dip_pct=self.dip_pct)

    def accepts(self, signal: dict) -> bool:
        if self.ordinary_only and signal.get("entry_signal") != "放量转强":
            return False
        conditions = (("max_drawdown_pct", self.max_drawdown_pct, False),
                      ("consolidation_volume_ratio", self.max_contraction, False),
                      ("probe_age_days", self.max_probe_age, False),
                      ("probe_volume_vs_ma5", self.max_probe_volume, False),
                      ("volume_vs_ma5", self.min_confirmation_volume, True))
        for key, threshold, minimum in conditions:
            if threshold is None:
                continue
            value = signal.get(key)
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value)):
                return False
            if (value < threshold if minimum else value > threshold):
                return False
        return True


TRIALS = (
    Trial("baseline"), Trial("dip_2", dip_pct=.02), Trial("dip_3", dip_pct=.03),
    Trial("ordinary_only", ordinary_only=True), Trial("drawdown_6", max_drawdown_pct=6),
    Trial("contraction_50", max_contraction=.5), Trial("age_8", max_probe_age=8),
    Trial("probe_volume_5", max_probe_volume=5),
    Trial("confirmation_volume_1_5", min_confirmation_volume=1.5),
    Trial("dip_2_drawdown_6", dip_pct=.02, max_drawdown_pct=6),
    Trial("dip_2_contraction_50", dip_pct=.02, max_contraction=.5),
)
MATURITY = TradePolicy().maturity_sessions


def truncate_stocks(stocks: dict[str, StockSeries], boundary: date) -> dict[str, StockSeries]:
    for stock in stocks.values():
        previous = None
        for bar in stock.bars:
            if bar.date is None or (previous is not None and bar.date <= previous):
                raise ValueError("Training requires ordered, dated bars; invalid chronology cannot be dropped")
            previous = bar.date
    return {symbol: stock.model_copy(update={"bars": [bar for bar in stock.bars
            if bar.date < boundary]}) for symbol, stock in stocks.items()}


def mature_rows(rows: list[dict], end_date: date | None = None) -> list[dict]:
    return [row for row in rows if row["available_future_sessions"] >= MATURITY
            and (end_date is None or date.fromisoformat(row["signal_date"]) <= end_date)]


def opportunity_metrics(rows: list[dict], original_signals: int, *, end_date: date | None = None) -> dict:
    mature = mature_rows(rows, end_date)
    summary = summarize_trades(mature)
    total = sum(row["net_return_pct"] for row in mature if row["status"] == "closed")
    return {**summary, "original_signals": original_signals,
            "filtered_signals": original_signals - len(mature),
            "return_per_original_signal_pct": round(total / original_signals, 4) if original_signals else None}


def _complete(stats: dict) -> bool:
    return not any(stats.get(key, 0) for key in ("open_trades", "entry_pending", "invalid_data"))


def select_training_trial(training: dict[str, dict]) -> str | None:
    """Do not accept validation results here: selection is fixed before inspection."""
    baseline = training["baseline"]
    if baseline["closed_trades"] < 30 or not _complete(baseline):
        return None
    eligible = []
    for order, (trial_id, stats) in enumerate(training.items()):
        if (trial_id == "baseline" or not _complete(stats) or stats["closed_trades"] < 30
                or stats["closed_trades"] < baseline["closed_trades"] * .35):
            continue
        if (stats["return_per_original_signal_pct"] is None or stats["mean_net_return_pct"] is None
                or stats["mean_net_return_pct"] <= 0
                or stats["return_per_original_signal_pct"] < baseline["return_per_original_signal_pct"] + .10
                or stats["mean_net_return_pct"] < baseline["mean_net_return_pct"] + .25):
            continue
        eligible.append((stats["return_per_original_signal_pct"], stats["mean_net_return_pct"], -order, trial_id))
    return max(eligible)[-1] if eligible else None


def paired_date_interval(baseline: list[dict], candidate: list[dict], *, repetitions: int = 4000,
                         end_date: date | None = None) -> dict:
    base = mature_rows(baseline, end_date)
    selected_rows = mature_rows(candidate, end_date)
    selected = {(row["symbol"], row["signal_date"]): row for row in selected_rows}
    clusters = defaultdict(lambda: [0.0, 0])
    for row in base:
        other = selected.get((row["symbol"], row["signal_date"]))
        left = row["net_return_pct"] if row["status"] == "closed" else 0
        right = other["net_return_pct"] if other and other["status"] == "closed" else 0
        clusters[row["signal_date"]][0] += right - left
        clusters[row["signal_date"]][1] += 1
    values = [clusters[key] for key in sorted(clusters)]
    point = sum(value[0] for value in values) / len(base) if base else None
    report = {"mean_difference_pct": round(point, 4) if point is not None else None,
              "date_clusters": len(values), "original_signals": len(base),
              "repetitions": repetitions, "seed": 711, "lower_pct": None, "upper_pct": None,
              "method": "Paired signal-date cluster percentile interval; exploratory, no multiple-trial correction"}
    if len(values) < 5 or not _complete(summarize_trades(base)) or not _complete(summarize_trades(selected_rows)):
        return report
    rng = random.Random(711)
    samples = []
    for _ in range(repetitions):
        draw = rng.choices(values, k=len(values))
        samples.append(sum(value[0] for value in draw) / sum(value[1] for value in draw))
    samples.sort()
    report.update(lower_pct=round(samples[int(.025 * (repetitions - 1))], 4),
                  upper_pct=round(samples[int(.975 * (repetitions - 1))], 4))
    return report


@dataclass
class ResearchWindows:
    training_stocks: dict[str, StockSeries]
    training_signals: list[dict]
    validation_signals: list[dict]


def prepare_windows(stocks: dict[str, StockSeries], history: list[MarketLineSnapshot],
                    train_start: date, validation_start: date) -> ResearchWindows:
    training_stocks = truncate_stocks(stocks, validation_start)
    return ResearchWindows(training_stocks,
        collect_signals(list(training_stocks.values()), history, train_start),
        collect_signals(list(stocks.values()), history, validation_start))


def _validation_status(baseline: dict, candidate: dict, interval: dict) -> str:
    if (candidate["closed_trades"] < 15 or candidate["closed_trades"] < baseline["closed_trades"] * .35
            or not _complete(candidate) or not _complete(baseline)):
        return "insufficient_validation"
    if (candidate["mean_net_return_pct"] <= baseline["mean_net_return_pct"]
            or candidate["return_per_original_signal_pct"] <= baseline["return_per_original_signal_pct"]):
        return "rejected_validation"
    if interval["lower_pct"] is None or interval["lower_pct"] <= 0:
        return "exploratory_improvement_uncertain"
    return "eligible_for_forward_test"


def run_experiment(stocks: dict[str, StockSeries], history: list[MarketLineSnapshot], *,
                   train_start: date, validation_start: date, require_sector: bool,
                   require_hot_theme: bool = False,
                   allow_sector_or_hot: bool = False,
                   validation_end: date = date(2026, 8, 10),
                   windows: ResearchWindows | None = None) -> dict:
    if validation_end < validation_start:
        raise ValueError("Validation end must not be before validation start")
    validate_cohort_options(require_sector=require_sector, require_hot_theme=require_hot_theme,
                            allow_sector_or_hot=allow_sector_or_hot)
    windows = windows or prepare_windows(stocks, history, train_start, validation_start)
    ledgers = {}
    metrics = {}
    denominators = {}
    for phase, signals, universe in (("training", windows.training_signals, windows.training_stocks),
                                     ("validation", windows.validation_signals, stocks)):
        end_date = validation_end if phase == "validation" else None
        denominators[phase] = sum(row["available_future_sessions"] >= MATURITY
                                 and (end_date is None or date.fromisoformat(row["signal_date"]) <= end_date)
                                 and cohort_signal_eligible(row, require_sector=require_sector,
                                     require_hot_theme=require_hot_theme, allow_sector_or_hot=allow_sector_or_hot) for row in signals)
        for trial in TRIALS:
            cohort = run_cohort([row for row in signals if trial.accepts(row)], universe,
                                trial.policy(), require_sector=require_sector, require_hot_theme=require_hot_theme,
                                allow_sector_or_hot=allow_sector_or_hot)
            ledgers[trial.id, phase] = cohort["trades"]
            metrics[trial.id, phase] = opportunity_metrics(cohort["trades"], denominators[phase], end_date=end_date)
    selected = select_training_trial({trial.id: metrics[trial.id, "training"] for trial in TRIALS})
    report = {
        "requires_confirmation_sector": require_sector and not allow_sector_or_hot,
        "requires_hot_theme": require_hot_theme and not allow_sector_or_hot,
        "accepts_sector_or_hot": allow_sector_or_hot,
        "training_signal_count": len(windows.training_signals),
        "validation_signal_count": len(windows.validation_signals),
        "training_sector_status_counts": dict(Counter(row["sector_status"] for row in windows.training_signals)),
        "validation_sector_status_counts": dict(Counter(row["sector_status"] for row in windows.validation_signals)),
        "selected_trial_id": selected, "selection_source": "training_mature_only",
        "assessment": "no_training_improvement" if denominators["training"] else "insufficient_training",
        "baseline": {phase: metrics["baseline", phase] for phase in ("training", "validation")},
        "trials": [{"definition": asdict(trial), **{phase: metrics[trial.id, phase]
                    for phase in ("training", "validation")},
                    "validation_all_observed": summarize_trades(ledgers[trial.id, "validation"])} for trial in TRIALS],
        "baseline_trades": {phase: ledgers["baseline", phase] for phase in ("training", "validation")},
        "selected_trades": {}, "paired_interval": None, "cost_stress": [], "validation_by_month": {},
        "entry_price_sensitivity": {trial_id: paired_date_interval(ledgers["baseline", "validation"],
                                   ledgers[trial_id, "validation"], end_date=validation_end)
                                   for trial_id in ("dip_2", "dip_3")},
        "production_defaults_changed": False,
    }
    if selected is None:
        return report
    trial = next(item for item in TRIALS if item.id == selected)
    report["selected_trades"] = {phase: ledgers[selected, phase] for phase in ("training", "validation")}
    interval = paired_date_interval(ledgers["baseline", "validation"], ledgers[selected, "validation"],
                                    end_date=validation_end)
    report["paired_interval"] = interval
    report["assessment"] = _validation_status(metrics["baseline", "validation"], metrics[selected, "validation"], interval)
    months = sorted({row["signal_date"][:7] for row in mature_rows(ledgers["baseline", "validation"], validation_end)})
    for month in months:
        base = [row for row in ledgers["baseline", "validation"] if row["signal_date"].startswith(month)]
        other = [row for row in ledgers[selected, "validation"] if row["signal_date"].startswith(month)]
        count = len(mature_rows(base, validation_end))
        report["validation_by_month"][month] = {"baseline": opportunity_metrics(base, count, end_date=validation_end),
                                                 "selected": opportunity_metrics(other, count, end_date=validation_end)}
    for multiplier in (1.5, 2.0):
        stress = {"cost_multiplier": multiplier}
        for label, item in (("baseline", TRIALS[0]), ("selected", trial)):
            policy = item.policy()
            policy = replace(policy, buy_fee_rate=policy.buy_fee_rate * multiplier,
                             sell_fee_rate=policy.sell_fee_rate * multiplier,
                             slippage_rate=policy.slippage_rate * multiplier)
            cohort = run_cohort([row for row in windows.validation_signals if item.accepts(row)], stocks,
                                policy, require_sector=require_sector, require_hot_theme=require_hot_theme,
                                allow_sector_or_hot=allow_sector_or_hot)
            stress[label] = opportunity_metrics(cohort["trades"], denominators["validation"], end_date=validation_end)
        report["cost_stress"].append(stress)
    return report


def load_history_snapshot(path: Path) -> tuple[list[MarketLineSnapshot], str, str | None, str | None]:
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return [], "missing", None, None
    except OSError as exc:
        return [], "invalid", str(exc), None
    digest = sha256(content).hexdigest()
    try:
        payload = json.loads(content)
        if not isinstance(payload, list):
            raise ValueError("Market-line history must be a JSON array")
        history = [MarketLineSnapshot.model_validate(item) for item in payload]
        return history, "loaded" if history else "empty", None, digest
    except (ValueError, TypeError, UnicodeError) as exc:
        return [], "invalid", str(exc), digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--snapshot", type=Path, default=root / "data/user-strategy/latest.json")
    parser.add_argument("--history", type=Path)
    parser.add_argument("--train-start", type=date.fromisoformat, default=date(2025, 9, 1))
    parser.add_argument("--validation-start", type=date.fromisoformat, default=date(2026, 6, 26))
    parser.add_argument("--validation-end", type=date.fromisoformat, default=date(2026, 8, 10),
                        help="Frozen mature signal cutoff; later signals remain observations")
    parser.add_argument("--include-unfiltered-diagnostic", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=root / "data/local-run-20261007/sector-or-hot-optimization")
    args = parser.parse_args(argv)
    if args.train_start >= args.validation_start:
        raise ValueError("Training start must be before validation start")
    if args.validation_end < args.validation_start:
        raise ValueError("Validation end must not be before validation start")
    history_path = args.history or args.snapshot.with_name("market-line-history.json")
    targets = [args.output_dir / name for name in ("summary.json", "trials.csv", "baseline-trades.csv", "selected-trades.csv")]
    if any(path.resolve() in (args.snapshot.resolve(), history_path.resolve()) for path in targets):
        raise ValueError("Output must not overwrite input files")
    snapshot_bytes = args.snapshot.read_bytes()
    raw = json.loads(snapshot_bytes)
    if raw.get("small_cap_status") != "ok" or not raw.get("small_cap_stocks"):
        raise ValueError("A nonempty successful small-cap snapshot is required")
    stocks = {row["symbol"]: StockSeries.model_validate(row) for row in raw["small_cap_stocks"]}
    as_of = max(bar.date for stock in stocks.values() for bar in stock.bars if bar.date is not None)
    if as_of < args.validation_start:
        raise ValueError("Validation start must not be after the supplied data")
    history, history_status, history_error, history_digest = load_history_snapshot(history_path)
    print("Scanning truncated training and later validation prices...", flush=True)
    windows = prepare_windows(stocks, history, args.train_start, args.validation_start)
    report = {
        "generated_at": datetime.now(UTC).isoformat(), "research_version": 3,
        "snapshot_path": str(args.snapshot.resolve()), "snapshot_sha256": sha256(snapshot_bytes).hexdigest(),
        "snapshot_generated_at": raw.get("small_cap_generated_at"), "as_of": as_of.isoformat(),
        "universe": len(stocks), "history_path": str(history_path.resolve()), "history_status": history_status,
        "history_error": history_error, "history_sha256": history_digest, "history_records": len(history),
        "train_start": args.train_start.isoformat(), "validation_start": args.validation_start.isoformat(),
        "validation_end": args.validation_end.isoformat(),
        "training_price_cutoff_exclusive": args.validation_start.isoformat(), "maturity_sessions": MATURITY,
        "trial_count": len(TRIALS), "execution_policy": asdict(TradePolicy()),
        "entry_cohort": "Sector effect OR documented top-20 concept gain rank on confirmation day",
        "selection_rules": {"minimum_training_closed": 30, "minimum_validation_closed": 15,
                            "minimum_closed_retention": .35, "minimum_training_signal_improvement_pp": .10,
                            "minimum_training_trade_improvement_pp": .25, "requires_positive_training_mean": True},
        "production_defaults_changed": False,
        "limitations": [
            "Fixed current-cap survivor universe, not point-in-time cap, ST status or membership",
            "Formal sector cohort requires actual dated evidence; missing history never falls back",
            "Hot-theme top-20 gain rank is an independent price-strength proxy, not social/news popularity; dated basis required",
            "Retrospective time split, not untouched out-of-sample: recent baseline was previously inspected",
            "Eleven prespecified trials; date-cluster interval is exploratory, not multiplicity-corrected",
            "Per-original-signal contribution is equal-weight event research, not portfolio or annualized return",
            "Training prices are truncated at cutoff; 33 future stock bars required in each period",
            "Period simulations start flat; positions before the validation start are not carried in",
            "QFQ bars approximate ticks/limits/T+1 execution; gap or blocked stop may lose more than 7%",
            "No intraday queues, lot sizes, minimum commissions, portfolio allocation or complete suspension calendar",
            "Incomplete mature trades block selection; their zero closed contribution is not a realized return",
        ],
        "requested_sector": run_experiment(stocks, history, train_start=args.train_start,
            validation_start=args.validation_start, validation_end=args.validation_end,
            require_sector=True, require_hot_theme=True, allow_sector_or_hot=True, windows=windows),
        "sector_only_diagnostic": run_experiment(stocks, history, train_start=args.train_start,
            validation_start=args.validation_start, validation_end=args.validation_end, require_sector=True, windows=windows),
    }
    if args.include_unfiltered_diagnostic:
        report["unfiltered_diagnostic"] = run_experiment(stocks, history, train_start=args.train_start,
            validation_start=args.validation_start, validation_end=args.validation_end, require_sector=False, windows=windows)
    trial_rows, baseline_rows, selected_rows = [], [], []
    for group in ("requested_sector", "sector_only_diagnostic", "unfiltered_diagnostic"):
        if group not in report:
            continue
        result = report[group]
        for trial in result["trials"]:
            for phase in ("training", "validation"):
                trial_rows.append({"group": group, "phase": phase, **trial["definition"], **trial[phase]})
        for field, output in (("baseline_trades", baseline_rows), ("selected_trades", selected_rows)):
            for phase, rows in result[field].items():
                output.extend({"group": group, "phase": phase, **row} for row in rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for target, rows in zip(targets[1:], (trial_rows, baseline_rows, selected_rows)):
        _write_csv(target, rows)
    overview = {key: value for key, value in report.items()
                if key not in ("requested_sector", "sector_only_diagnostic", "unfiltered_diagnostic")}
    overview["output_dir"] = str(args.output_dir.resolve())
    for group in ("requested_sector", "sector_only_diagnostic", "unfiltered_diagnostic"):
        if group in report:
            result = report[group]
            overview[group] = {key: value for key, value in result.items()
                               if key not in ("trials", "baseline_trades", "selected_trades", "validation_by_month", "cost_stress")}
            overview[group]["selected_metrics"] = next((row for row in result["trials"]
                if row["definition"]["id"] == result["selected_trial_id"]), None)
    print(json.dumps(overview, ensure_ascii=True, indent=2, allow_nan=False))
    return report


if __name__ == "__main__":
    main()
