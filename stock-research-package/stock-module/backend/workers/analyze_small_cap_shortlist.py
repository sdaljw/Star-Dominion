"""Read-only morphology audit; fixed current-cap universe, not a return backtest."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from statistics import mean, median

from app.domain.small_cap_probe import track_probe
from app.domain.strategies import StockSeries, evaluate_small_cap_absorption


def measurements(stock, factors):
    bars = stock.bars
    index = next(i for i, b in enumerate(bars) if b.date.isoformat() == factors["probe_date"])
    probe = bars[index]
    following = bars[index + 1:]
    spread = probe.high - probe.low
    return {
        "probe_pct": probe.pct,
        "probe_ma5": probe.volume / (sum(b.volume for b in bars[index - 5:index]) / 5),
        "close_location": (probe.close - probe.low) / spread if spread else 1,
        "age": len(following),
        "contraction": (sum(b.volume for b in following[-2:]) / 2 / probe.volume
                        if len(following) >= 2 else 99),
        "drawdown": factors["max_drawdown_pct"],
        "gain": (bars[-1].close / probe.close - 1) * 100,
        "support": bars[-1].close / probe.open,
    }


def filters(metrics, factors):
    quality = (metrics["probe_ma5"] >= 2 and metrics["probe_pct"] >= 2
               and metrics["close_location"] >= .6)
    fresh = metrics["age"] <= 12
    controlled = metrics["drawdown"] <= 10 and metrics["gain"] <= 6 and metrics["support"] >= .99
    ready = metrics["age"] >= 2 and metrics["drawdown"] >= 2 and metrics["contraction"] <= .65
    alert = factors["alert_active"]
    return {
        "quality": quality,
        "quality_fresh": quality and fresh,
        "quality_fresh_controlled": quality and fresh and controlled,
        "strict": quality and fresh and controlled and (ready or alert) and factors["stage"] != "tracking",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--snapshot", type=Path, default=root / "data/user-strategy/latest.json")
    parser.add_argument("--events", type=Path, default=root / "data/local-run-20260926/limitup-streak-events.csv")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--outcomes", action="store_true", help="Legacy fixed-horizon benchmark; use backtest_small_cap_policy for trade returns")
    args = parser.parse_args()
    raw = json.loads(args.snapshot.read_text(encoding="utf-8"))
    stocks = {row["symbol"]: StockSeries.model_validate(row) for row in raw["small_cap_stocks"]}
    counts, stages, production_stages, rejected, selected = Counter(), Counter(), Counter(), Counter(), []
    for stock in stocks.values():
        result = track_probe(stock)
        production = evaluate_small_cap_absorption(stock)
        if production.matched:
            counts["production_v4"] += 1
            production_stages[production.factors["stage"]] += 1
            selected.append({"symbol": stock.symbol, "name": stock.name, **production.factors})
        else:
            rejected.update(production.risk_flags or ["no_qualified_probe"])
        if not result.matched:
            continue
        counts["broad"] += 1
        stages[result.factors["stage"]] += 1
        metrics = measurements(stock, result.factors)
        gates = filters(metrics, result.factors)
        counts.update(k for k, ok in gates.items() if ok)
    cohorts = {}
    with args.events.open(encoding="utf-8-sig", newline="") as handle:
        events = list(csv.DictReader(handle))
    for event in events:
        stock = stocks.get(event["symbol"][-6:])
        if not stock or "ST" in stock.name.upper() or "退" in stock.name:
            continue
        start = next((i for i, b in enumerate(stock.bars) if b.date.isoformat() == event["streak_start"]), None)
        if start is None or start < 25 or event["streak_start"] < "2026-06-26":
            continue
        cohort = "4plus" if int(event["total_consecutive_boards"]) >= 4 else "2to3"
        bucket = cohorts.setdefault(cohort, Counter())
        bucket["episodes"] += 1
        seen = set()
        for end in range(max(25, start - 14), start + 1):
            prefix = stock.model_copy(update={"bars": stock.bars[:end]})
            production = evaluate_small_cap_absorption(prefix)
            if production.matched:
                seen.add("production_v4")
            result = track_probe(prefix)
            if result.matched:
                seen.add("broad")
                seen.update(k for k, ok in filters(measurements(prefix, result.factors), result.factors).items() if ok)
        bucket.update(seen)
    output = {"as_of": max(s.bars[-1].date.isoformat() for s in stocks.values()),
                      "universe": len(stocks), "counts": counts, "stages": stages,
                      "production_stages": production_stages,
                      "rejected": rejected, "leader_episode_retention": cohorts,
                      "selected": selected if args.details else len(selected)}
    if args.outcomes:
        output["outcome_method"] = "legacy_fixed_horizon; superseded by workers.backtest_small_cap_policy"
        outcomes = {key: [] for key in ("v3_watch", "v3_confirm", "v4_watch", "v4_confirm", "v4_first_board", "v4_second_board")}
        unfilled = Counter()
        signal_dates = []
        for stock in stocks.values():
            seen = {key: set() for key in outcomes}
            for index in range(25, len(stock.bars) - 20):
                day = stock.bars[index].date.isoformat()
                if day < "2026-06-26":
                    continue
                prefix = stock.model_copy(update={"bars": stock.bars[:index + 1]})
                for version, evaluator in (("v3", track_probe), ("v4", evaluate_small_cap_absorption)):
                    result = evaluator(prefix)
                    probe = result.factors.get("probe_date")
                    if not result.matched:
                        continue
                    keys = [f"{version}_watch"]
                    if result.factors["alert_active"]:
                        keys.append(f"{version}_confirm")
                        if version == "v4" and result.factors["entry_signal"] in ("首板确认", "二板确认"):
                            keys.append("v4_first_board" if result.factors["entry_signal"] == "首板确认" else "v4_second_board")
                    future = stock.bars[index + 1:index + 21]
                    for key in keys:
                        if probe in seen[key]:
                            continue
                        seen[key].add(probe)
                        entry = future[0].open
                        # A queued buy at the upper limit is not a known executable entry.
                        if entry / stock.bars[index].close >= 1.098:
                            unfilled[key] += 1
                            continue
                        outcomes[key].append({
                            **{f"return_{horizon}": (future[horizon - 1].close * .999 / (entry * 1.001) - 1) * 100
                               for horizon in (5, 10, 20)},
                            "mae": max(0, 1 - min(b.low for b in future) / entry) * 100,
                        })
                        signal_dates.append(day)
        output["outcomes_20_sessions"] = {
            key: {"episodes": len(values), "unfilled_upper_limit": unfilled[key],
                  **{f"{stat}_{horizon}d_pct": round(fn(v[f"return_{horizon}"] for v in values), 4)
                     for stat, fn in (("mean", mean), ("median", median)) for horizon in (5, 10, 20)},
                  "positive_20d_pct": round(mean(v["return_20"] > 0 for v in values) * 100, 2),
                  "median_mae_20d_pct": round(median(v["mae"] for v in values), 4)}
            for key, values in outcomes.items() if values}
        output["execution_assumptions"] = "next session open; entry/exit cost 0.1% each; upper-limit open excluded; overlapping episodes, no portfolio simulation"
        output["outcome_signal_window"] = [min(signal_dates), max(signal_dates)] if signal_dates else []
    print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
