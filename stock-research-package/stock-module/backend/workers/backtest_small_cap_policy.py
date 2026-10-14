"""Read-only first-confirmation trade replay, with explicit historical sector coverage."""

import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import date, datetime, UTC
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median

from app.domain.market_lines import MarketLineSnapshot
from app.domain.probe_sector import build_probe_sector_context
from app.domain.small_cap_entry import build_small_cap_entry_gate
from app.domain.small_cap_backtest import TradePolicy, replay_trade
from app.domain.strategies import StockSeries, evaluate_small_cap_absorption
from app.repositories.market_lines import MarketLineHistoryRepository


def collect_signals(stocks: list[StockSeries], history: list[MarketLineSnapshot],
                    start_date: date) -> list[dict]:
    signals = []
    for stock in stocks:
        seen = set()
        for index in range(len(stock.bars)):
            day = stock.bars[index].date
            if day is None or day < start_date:
                continue
            prefix = stock.model_copy(update={"bars": stock.bars[:index + 1]})
            result = evaluate_small_cap_absorption(prefix)
            factors = result.factors
            probe = factors.get("probe_date")
            if (not result.matched or not factors.get("alert_active") or probe in seen
                    or factors.get("confirmation_date") != day.isoformat()):
                continue
            seen.add(probe)
            context = build_probe_sector_context(prefix, factors, history)
            signals.append({
                "symbol": stock.symbol, "name": stock.name, "signal_index": index,
                "signal_date": day.isoformat(), "available_future_sessions": len(stock.bars) - index - 1,
                **factors, **context,
                **build_small_cap_entry_gate({**factors, **context}),
                "sector_status": context.get("confirmation_sector_status", "unavailable"),
                "sector_name": context.get("confirmation_sector_name", ""),
                "sector_cycle_confirmed": context.get("confirmation_sector_cycle_confirmed", False),
                "sector_ladder_confirmed": context.get("confirmation_sector_ladder_confirmed", False),
                "hot_theme_cycle_confirmed": context.get("confirmation_hot_theme_cycle_confirmed", False),
                "hot_theme_ladder_confirmed": context.get("confirmation_hot_theme_ladder_confirmed", False),
            })
    return sorted(signals, key=lambda row: (row["signal_date"], row["symbol"]))


def summarize_trades(trades: list[dict]) -> dict:
    counts = Counter(row["status"] for row in trades)
    closed = [row for row in trades if row["status"] == "closed"]
    returns = [row["net_return_pct"] for row in closed]
    gains = sum(value for value in returns if value > 0)
    losses = -sum(value for value in returns if value < 0)
    winning = [value for value in returns if value > 0]
    losing = [value for value in returns if value < 0]
    open_marks = [row["mark_return_pct"] for row in trades if row["status"] == "open"
                  and row.get("mark_return_pct") is not None]
    worst = [row["worst_close_return_pct"] for row in closed if row.get("worst_close_return_pct") is not None]
    return {
        "signals": len(trades), "closed_trades": counts["closed"], "open_trades": counts["open"],
        "unfilled_entries": counts["unfilled"], "entry_pending": counts["entry_pending"],
        "overlap_skipped": counts["overlap_skipped"], "invalid_data": counts["invalid_data"],
        "mean_net_return_pct": round(mean(returns), 4) if returns else None,
        "median_net_return_pct": round(median(returns), 4) if returns else None,
        "win_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else None,
        "mean_holding_sessions": round(mean(row["holding_sessions"] for row in closed), 2) if closed else None,
        "profit_factor": round(gains / losses, 4) if losses else None,
        "best_net_return_pct": round(max(returns), 4) if returns else None,
        "worst_net_return_pct": round(min(returns), 4) if returns else None,
        "mean_winning_return_pct": round(mean(winning), 4) if winning else None,
        "mean_losing_return_pct": round(mean(losing), 4) if losing else None,
        "mean_open_mark_return_pct": round(mean(open_marks), 4) if open_marks else None,
        "worst_open_mark_return_pct": round(min(open_marks), 4) if open_marks else None,
        "median_worst_close_return_pct": round(median(worst), 4) if worst else None,
        "exit_reason_counts": dict(Counter(row["exit_reason"] for row in closed)),
        "blocked_exit_sessions": sum(row.get("blocked_exit_sessions", 0) for row in trades),
        "profit_orders_cancelled": sum(row.get("profit_orders_cancelled", 0) for row in trades),
    }


def validate_cohort_options(*, require_sector: bool, require_hot_theme: bool, allow_sector_or_hot: bool) -> None:
    if require_hot_theme and not require_sector:
        raise ValueError("Hot-theme qualification requires sector qualification")
    if allow_sector_or_hot and not (require_sector and require_hot_theme):
        raise ValueError("Sector OR hot requires both evidence channels enabled")


def cohort_signal_eligible(row: dict, *, require_sector: bool, require_hot_theme: bool = False,
                           allow_sector_or_hot: bool = False) -> bool:
    validate_cohort_options(require_sector=require_sector, require_hot_theme=require_hot_theme,
                            allow_sector_or_hot=allow_sector_or_hot)
    if allow_sector_or_hot:
        return build_small_cap_entry_gate(row)["entry_eligible"] is True
    if require_hot_theme:
        gate = build_small_cap_entry_gate(row)
        return (gate["entry_sector_qualified"] is True and gate["entry_hot_theme_qualified"] is True
                and row.get("confirmation_hot_theme_sector_confirmed") is True)
    return not require_sector or row["sector_status"] == "confirmed"


def run_cohort(signals: list[dict], stocks: dict[str, StockSeries], policy: TradePolicy,
               *, require_sector: bool, require_hot_theme: bool = False, allow_sector_or_hot: bool = False) -> dict:
    validate_cohort_options(require_sector=require_sector, require_hot_theme=require_hot_theme,
                            allow_sector_or_hot=allow_sector_or_hot)
    eligible = [row for row in signals if cohort_signal_eligible(row, require_sector=require_sector,
                require_hot_theme=require_hot_theme, allow_sector_or_hot=allow_sector_or_hot)]
    reserved_until = {}
    trades = []
    for signal in sorted(eligible, key=lambda row: (row["signal_date"], row["symbol"])):
        symbol, index = signal["symbol"], signal["signal_index"]
        stock = stocks[symbol]
        if index < reserved_until.get(symbol, -1):
            trades.append({**signal, "status": "overlap_skipped"})
            continue
        try:
            replay = replay_trade(stock, index, policy)
        except ValueError as exc:
            trades.append({**signal, "status": "invalid_data", "error": str(exc)})
            continue
        reserved_until[symbol] = replay.reserved_until_index
        trade = {**signal, **asdict(replay)}
        for label in ("entry", "exit", "stop_trigger"):
            position = trade[f"{label}_index"]
            trade[f"{label}_date"] = stock.bars[position].date.isoformat() if position is not None else None
        trades.append(trade)
    mature = [row for row in trades if row["available_future_sessions"] >= policy.maturity_sessions]
    def group_flag(row, kind):
        if allow_sector_or_hot:
            return row.get(f"sector_{kind}_confirmed") or row.get(f"hot_theme_{kind}_confirmed")
        return row.get(f"{'hot_theme' if require_hot_theme else 'sector'}_{kind}_confirmed")
    return {
        "requires_confirmation_sector": require_sector and not allow_sector_or_hot,
        "requires_hot_theme": require_hot_theme and not allow_sector_or_hot,
        "accepts_sector_or_hot": allow_sector_or_hot,
        "entry_basis_counts": dict(Counter(build_small_cap_entry_gate(row)["entry_basis"] for row in eligible)),
        "signal_count": len(signals), "eligible_signals": len(eligible),
        "sector_status_counts": dict(Counter(row["sector_status"] for row in signals)),
        "hot_theme_status_counts": dict(Counter(row.get("confirmation_hot_theme_status", "unavailable") for row in signals)),
        "maturity_required_future_sessions": policy.maturity_sessions,
        "all_observed": summarize_trades(trades), "mature": summarize_trades(mature),
        "mature_by_entry_signal": {key: summarize_trades([row for row in mature if row["entry_signal"] == key])
                                  for key in sorted({row["entry_signal"] for row in mature})},
        "mature_sector_groups": {
            "cycle": summarize_trades([row for row in mature if group_flag(row, "cycle")]),
            "ladder": summarize_trades([row for row in mature if group_flag(row, "ladder")]),
            "cycle_and_ladder": summarize_trades([row for row in mature if group_flag(row, "cycle") and group_flag(row, "ladder")]),
        },
        "trades": trades,
    }


def load_history(path: Path) -> tuple[list[MarketLineSnapshot], str, str | None]:
    if not path.exists():
        return [], "missing", None
    try:
        snapshots = MarketLineHistoryRepository(path).load()
        return snapshots, "loaded" if snapshots else "empty", None
    except (OSError, ValueError) as exc:
        return [], "invalid", str(exc)


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["symbol", "signal_date", "status"])
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--snapshot", type=Path, default=root / "data/user-strategy/latest.json")
    parser.add_argument("--history", type=Path)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 26))
    parser.add_argument("--dip-pct", type=float, default=.01, help="Fraction below signal close, e.g. 0.01")
    parser.add_argument("--buy-fee-rate", type=float, default=.001)
    parser.add_argument("--sell-fee-rate", type=float, default=.001)
    parser.add_argument("--slippage-rate", type=float, default=.0005)
    parser.add_argument("--stop-loss-pct", type=float, default=.07, help="Net-cost stop fraction, default 0.07")
    parser.add_argument("--no-stop-loss", action="store_true", help="Disable stop for a separate original-policy baseline")
    parser.add_argument("--include-unfiltered-diagnostic", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=root / "data/local-run-20261007/trade-policy-sector-or-hot")
    args = parser.parse_args(argv)
    policy = TradePolicy(dip_pct=args.dip_pct, buy_fee_rate=args.buy_fee_rate,
                         sell_fee_rate=args.sell_fee_rate, slippage_rate=args.slippage_rate,
                         stop_loss_pct=None if args.no_stop_loss else args.stop_loss_pct)
    snapshot_bytes = args.snapshot.read_bytes()
    raw = json.loads(snapshot_bytes)
    if raw.get("small_cap_status") != "ok" or not raw.get("small_cap_stocks"):
        raise ValueError("A nonempty successful small-cap snapshot is required")
    stocks = {row["symbol"]: StockSeries.model_validate(row) for row in raw["small_cap_stocks"]}
    history_path = args.history or args.snapshot.with_name("market-line-history.json")
    history, history_status, history_error = load_history(history_path)
    try:
        history_digest = sha256(history_path.read_bytes()).hexdigest()
    except OSError:
        history_digest = None
    signals = collect_signals(list(stocks.values()), history, args.start)
    report = {
        "generated_at": datetime.now(UTC).isoformat(), "policy_version": 4,
        "snapshot_path": str(args.snapshot.resolve()), "snapshot_sha256": sha256(snapshot_bytes).hexdigest(),
        "snapshot_generated_at": raw.get("small_cap_generated_at"),
        "as_of": max(stock.bars[-1].date.isoformat() for stock in stocks.values() if stock.bars),
        "signal_start": args.start.isoformat(), "universe": len(stocks), "signals": len(signals),
        "history_path": str(history_path.resolve()), "history_status": history_status,
        "history_error": history_error, "history_records": len(history),
        "history_sha256": history_digest,
        "execution_policy": asdict(policy),
        "entry_cohort": "Contemporaneous sector peers OR documented top-20 concept gain rank on first confirmation",
        "signal_definition": "First V4-qualified confirmation, observable on confirmation day, once per probe",
        "profit_exit": "After profitable close, next open only if net proceeds remain above cost",
        "mandatory_exit": "Next open after broken owned streak or 30th holding-session close; lower-limit open deferred",
        "stop_loss": "Fixed net-cost stop from T+1: gap at actual open, otherwise first intraday stop-price touch; lower-limit open deferred"
                     if policy.stop_loss_pct is not None else "disabled baseline",
        "limitations": [
            "Fixed current-cap universe, not point-in-time historical cap or membership; survivorship and cap bias",
            "Sector evidence requires dated membership and peers, unavailable history is not no sector effect",
            "Hotness is an independent top-20 concept gain-rank proxy, not news/social popularity or net inflow rank",
            "Entry eligibility uses confirmation-close evidence, not a fresh intraday check on every dip-entry day",
            "Daily QFQ bars approximate price limits and ticks; intraday ordering and execution queues unknown",
            "Stock bar count, not complete exchange calendar during suspensions",
            "Equal-weight trade statistics, not portfolio, annualized or compounded returns",
            "Next-open profit sale cannot be cancelled using a later same-day board; intraday highs are not picked",
            "Mature cohort requires 33 future sessions; open and pending trades are retained separately",
            "Stop price rounded down on QFQ cents; gap, T+1 or lower-limit deferral can lose more than the stop fraction",
            "Entry-day intraday lows are not retroactively used to sell; a closing breach queues next-open stop",
        ],
        "requested_sector": run_cohort(signals, stocks, policy, require_sector=True, require_hot_theme=True,
                                        allow_sector_or_hot=True),
        "sector_only_diagnostic": run_cohort(signals, stocks, policy, require_sector=True),
    }
    if args.include_unfiltered_diagnostic:
        report["unfiltered_diagnostic"] = run_cohort(signals, stocks, policy, require_sector=False)
    targets = [args.output_dir / name for name in
               ("summary.json", "signals.csv", "requested-sector-trades.csv", "unfiltered-diagnostic-trades.csv",
                "sector-only-diagnostic-trades.csv")]
    if any(path.resolve() in (args.snapshot.resolve(), history_path.resolve()) for path in targets):
        raise ValueError("Output must not overwrite input files")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    _write_csv(targets[1], signals)
    _write_csv(targets[2], report["requested_sector"]["trades"])
    _write_csv(targets[4], report["sector_only_diagnostic"]["trades"])
    if args.include_unfiltered_diagnostic:
        _write_csv(targets[3], report["unfiltered_diagnostic"]["trades"])
    compact = {**report, "output_dir": str(args.output_dir.resolve())}
    for key in ("requested_sector", "sector_only_diagnostic", "unfiltered_diagnostic"):
        if key in compact:
            compact[key] = {field: value for field, value in compact[key].items() if field != "trades"}
    print(json.dumps(compact, ensure_ascii=True, indent=2, allow_nan=False))
    return report


if __name__ == "__main__":
    main()
