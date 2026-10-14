"""Point-in-time sector evidence for the probe and confirmation sessions."""

from datetime import date
from collections.abc import Mapping, Sequence
from zoneinfo import ZoneInfo

from app.domain.market_lines import MarketLineEntry, MarketLineMember, MarketLineSnapshot
from app.domain.stocks import InvalidMainBoardSymbol, normalize_symbol
from app.domain.strategies import StockSeries

HOT_THEME_MAX_RANK = 20


def _hot_rank(snapshot: MarketLineSnapshot, line: MarketLineEntry) -> int | None:
    if snapshot.hot_rank_basis != "concept_gain_rank":
        return None
    acquired = snapshot.concept_acquired_at
    generated = snapshot.generated_at
    if acquired is None or acquired.tzinfo is None or generated is None or generated.tzinfo is None:
        return None
    acquired = acquired.astimezone(ZoneInfo("Asia/Shanghai"))
    if acquired.date() != snapshot.as_of_date or acquired.hour < 15 or acquired > generated:
        return None
    rank = snapshot.hot_concept_ranks.get(line.name, line.source_rank)
    return rank if isinstance(rank, int) and not isinstance(rank, bool) and rank > 0 else None


def _peer_evidence(line: MarketLineEntry, symbol: str) -> tuple[bool, list[MarketLineMember], dict[str, int]]:
    peers = []
    seen = set()
    for member in line.members:
        try:
            code = normalize_symbol(member.symbol)
        except InvalidMainBoardSymbol:
            continue
        if (code == symbol or code in seen or "ST" in member.name.upper() or "退" in member.name
                or not 0 < member.market_cap_yuan < 10_000_000_000 or not 9.8 <= member.pct <= 10.2):
            continue
        seen.add(code)
        peers.append(member)
    tiers = {"first_board": 0, "second_board": 0, "three_plus_board": 0}
    for member in peers:
        key = "first_board" if member.consecutive_boards == 1 else (
            "second_board" if member.consecutive_boards == 2 else "three_plus_board")
        tiers[key] += 1
    strong = line.pct > 0 and line.breadth_score >= 60 and len(peers) >= 2
    return strong, peers, tiers


def build_probe_sector_context(
    stock: StockSeries,
    factors: Mapping[str, float | int | bool | str],
    history: Sequence[MarketLineSnapshot],
) -> dict[str, float | int | bool | str]:
    """Missing membership or same-session history is unknown, never negative proof."""
    snapshots: dict[date, MarketLineSnapshot] = {}
    shanghai = ZoneInfo("Asia/Shanghai")
    for snapshot in history:
        if snapshot.status != "fresh" or snapshot.as_of_date is None or snapshot.generated_at is None:
            continue
        generated = snapshot.generated_at
        local = generated.replace(tzinfo=shanghai) if generated.tzinfo is None else generated.astimezone(shanghai)
        if local.date() != snapshot.as_of_date or local.hour < 15:
            continue
        previous = snapshots.get(snapshot.as_of_date)
        if previous is None or local > previous.generated_at:
            snapshots[snapshot.as_of_date] = snapshot.model_copy(update={"generated_at": local})

    context: dict[str, float | int | bool | str] = {}
    symbol = normalize_symbol(stock.symbol)
    sessions = sorted({bar.date for bar in stock.bars if bar.date is not None})
    for prefix, date_key in (("probe", "probe_date"), ("confirmation", "confirmation_date")):
        value = factors.get(date_key)
        if not value:
            continue
        key = f"{prefix}_sector_"
        hot_key = f"{prefix}_hot_theme_"
        context[key + "status"] = "unavailable"
        context[hot_key + "status"] = "unavailable"
        try:
            signal_date = date.fromisoformat(str(value))
        except ValueError:
            continue
        snapshot = snapshots.get(signal_date)
        if snapshot is None or signal_date not in sessions:
            continue
        evidence_lines = snapshot.evidence_lines if snapshot.evidence_lines is not None else snapshot.lines
        lines = [line for line in evidence_lines if symbol in line.eligible_member_symbols]
        if not lines:
            continue
        context[key + "status"] = "not_confirmed"
        if all(_hot_rank(snapshot, line) is not None for line in lines):
            context[hot_key + "status"] = "not_confirmed"
        window = [day for day in sessions if day <= signal_date][-5:]
        choices = []
        hot_choices = []
        for line in lines:
            strong, peers, tiers = _peer_evidence(line, symbol)
            active_dates = []
            for day in window:
                prior = snapshots.get(day)
                if prior and any((item.code, item.name) == (line.code, line.name)
                                 and _peer_evidence(item, symbol)[0]
                                 for item in (prior.evidence_lines if prior.evidence_lines is not None else prior.lines)):
                    active_dates.append(day)
            ladder = strong and sum(count > 0 for count in tiers.values()) >= 2
            cycle = strong and len(active_dates) >= 3
            peers.sort(key=lambda member: (-member.consecutive_boards, member.symbol))
            evidence = {
                "status": "confirmed", "name": line.name, "date": signal_date.isoformat(),
                "evidence_start": min(active_dates).isoformat() if active_dates else signal_date.isoformat(),
                "cycle_days": len(active_dates), "pct": line.pct,
                "cycle_confirmed": cycle, "ladder_confirmed": ladder, "breadth_pct": line.breadth_score,
                "peer_limitups": len(peers),
                "peers": "、".join(f"{member.name}{member.consecutive_boards}板" for member in peers[:3]),
                "source": snapshot.source or "历史主线快照",
            }
            priority = (cycle, ladder, len(peers), line.breadth_score, -line.rank)
            if strong:
                choices.append((priority, evidence))
            rank = _hot_rank(snapshot, line)
            if rank is not None and rank <= HOT_THEME_MAX_RANK:
                hot_choices.append(((strong, *priority, -rank), {**evidence, "rank": rank,
                    "basis": "concept_gain_rank", "sector_confirmed": strong}))
        if choices:
            context.update({key + field: value for field, value in max(choices, key=lambda item: item[0])[1].items()})
        if hot_choices:
            context.update({hot_key + field: value for field, value in max(hot_choices, key=lambda item: item[0])[1].items()})
    return context
