"""Explainable market-mainline scores and mainboard limit-up ladders."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
import math
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.stocks import InvalidMainBoardSymbol, normalize_symbol


SMALL_CAP_LIMIT_YUAN = 10_000_000_000
MAX_LINES = 5
PERSISTENCE_SESSIONS = 5


class ConceptMarketMember(BaseModel):
    symbol: str
    name: str
    pct: float


class ConceptMarketInput(BaseModel):
    name: str
    code: str
    hot_rank: int = Field(default=0, ge=0)
    pct: float
    turnover_yi: float
    up_count: int = Field(ge=0)
    down_count: int = Field(ge=0)
    members: list[ConceptMarketMember] = Field(default_factory=list)


class MarketEnvironment(BaseModel):
    label: Literal["偏弱", "中性", "偏强", "暂无数据"]
    advancing: int = Field(default=0, ge=0)
    declining: int = Field(default=0, ge=0)
    flat: int = Field(default=0, ge=0)
    limit_up_count: int = Field(default=0, ge=0)


class MarketLineMember(BaseModel):
    symbol: str
    name: str
    pct: float
    consecutive_boards: int = Field(ge=1)
    market_cap_yuan: float


class MarketLineEntry(BaseModel):
    name: str
    code: str
    source_rank: int = Field(default=0, ge=0)
    score: float = Field(ge=0, le=100)
    label: Literal["持续主线", "主线候选", "快速轮动", "观察"]
    rank: int = Field(ge=1)
    pct: float
    turnover_yi: float
    up_count: int = Field(ge=0)
    down_count: int = Field(ge=0)
    breadth_score: float = Field(ge=0, le=100)
    persistence_count: int = Field(ge=0, le=PERSISTENCE_SESSIONS)
    ladder_score: float = Field(ge=0, le=100)
    activity_score: float = Field(ge=0, le=100)
    ladder_tiers: dict[str, int]
    known_bar_count: int = Field(ge=0)
    eligible_small_cap_count: int = Field(ge=0)
    eligible_member_symbols: list[str] = Field(default_factory=list)
    members: list[MarketLineMember] = Field(default_factory=list)


class MarketLineSnapshot(BaseModel):
    status: Literal["fresh", "stale", "unavailable"]
    as_of_date: date | None
    generated_at: datetime | None
    source: str | None
    market_environment: MarketEnvironment
    hot_concept_ranks: dict[str, int] = Field(default_factory=dict)
    hot_rank_basis: Literal["concept_gain_rank", "unavailable"] = "unavailable"
    concept_acquired_at: datetime | None = None
    lines: list[MarketLineEntry] = Field(default_factory=list)
    evidence_lines: list[MarketLineEntry] | None = None


def classify_market_environment(advancing: int, declining: int) -> str:
    total = max(advancing, 0) + max(declining, 0)
    if total == 0:
        return "暂无数据"
    breadth = max(advancing, 0) / total
    if breadth < 0.4:
        return "偏弱"
    if breadth >= 0.6:
        return "偏强"
    return "中性"


def build_limitup_ladder(
    concept_members: Sequence[ConceptMarketMember],
    small_cap_rows: Sequence[Mapping[str, object]],
    as_of_date: date,
) -> tuple[dict[str, int], list[MarketLineMember], int, int, list[str]]:
    """Count consecutive mainboard limit-ups for concept members with fresh bars."""
    rows_by_symbol: dict[str, Mapping[str, object]] = {}
    for row in small_cap_rows:
        try:
            symbol = normalize_symbol(str(row.get("symbol", "")))
        except InvalidMainBoardSymbol:
            continue
        rows_by_symbol[symbol] = row

    tiers = {"first_board": 0, "second_board": 0, "three_plus_board": 0}
    eligible_small_cap_count = 0
    known_bar_count = 0
    eligible_symbols: list[str] = []
    leaders: list[MarketLineMember] = []
    seen: set[str] = set()

    for member in concept_members:
        try:
            symbol = normalize_symbol(member.symbol)
        except InvalidMainBoardSymbol:
            continue
        if symbol in seen or "ST" in member.name.upper() or "退" in member.name:
            continue
        seen.add(symbol)
        row = rows_by_symbol.get(symbol)
        if row is None or "ST" in str(row.get("name", "")).upper() or "退" in str(row.get("name", "")):
            continue
        market_cap = _number(row.get("market_cap"))
        if market_cap is None or not 0 < market_cap < SMALL_CAP_LIMIT_YUAN:
            continue
        eligible_small_cap_count += 1

        bars_raw = row.get("bars")
        if not isinstance(bars_raw, Sequence) or isinstance(bars_raw, (str, bytes)):
            continue
        dated_bars = [
            (bar_date, bar)
            for bar in bars_raw
            if isinstance(bar, Mapping)
            and (bar_date := _bar_date(bar.get("date"))) is not None
            and bar_date <= as_of_date
        ]
        if not dated_bars:
            continue
        dated_bars.sort(key=lambda item: item[0])
        latest_date, latest_bar = dated_bars[-1]
        if latest_date != as_of_date:
            continue
        eligible_symbols.append(symbol)
        latest_close = _number(latest_bar.get("close"))
        latest_high = _number(latest_bar.get("high"))
        latest_pct = _number(latest_bar.get("pct"))
        if latest_close is None or latest_high is None or latest_pct is None:
            continue
        known_bar_count += 1

        consecutive = 0
        for _, bar in reversed(dated_bars):
            close = _number(bar.get("close"))
            high = _number(bar.get("high"))
            pct = _number(bar.get("pct"))
            if (close is None or high is None or pct is None
                    or not 9.8 <= pct <= 10.2
                    or not math.isclose(close, high, abs_tol=0.011)):
                break
            consecutive += 1
        if consecutive == 0:
            continue
        tier = "first_board" if consecutive == 1 else (
            "second_board" if consecutive == 2 else "three_plus_board"
        )
        tiers[tier] += 1
        leaders.append(MarketLineMember(
            symbol=symbol,
            name=str(row.get("name") or member.name),
            pct=latest_pct,
            consecutive_boards=consecutive,
            market_cap_yuan=market_cap,
        ))

    leaders.sort(key=lambda item: (-item.consecutive_boards, -item.pct, item.symbol))
    return tiers, leaders, known_bar_count, eligible_small_cap_count, eligible_symbols


def score_market_lines(
    concepts: Sequence[ConceptMarketInput],
    history: Sequence[MarketLineSnapshot],
    small_cap_rows: Sequence[Mapping[str, object]],
    market_environment: MarketEnvironment,
    as_of_date: date,
    generated_at: datetime,
    *,
    concept_acquired_at: datetime | None = None,
) -> MarketLineSnapshot:
    """Score the current THS concepts and attach the small-cap mainboard ladder."""
    hot_ranks = {concept.name: concept.hot_rank for concept in concepts if concept.hot_rank > 0}
    session_dates = _market_session_dates(small_cap_rows, as_of_date)
    prior_session_dates = session_dates[-PERSISTENCE_SESSIONS:-1]
    ranks_by_date = {
        item.as_of_date: item.hot_concept_ranks
        for item in history
        if item.as_of_date is not None and item.as_of_date < as_of_date
    }
    pct_values = [concept.pct for concept in concepts]
    turnover_values = [concept.turnover_yi for concept in concepts]

    entries: list[MarketLineEntry] = []
    for concept in concepts:
        tiers, members, known_bars, eligible_members, eligible_symbols = build_limitup_ladder(
            concept.members, small_cap_rows, as_of_date,
        )
        breadth_total = concept.up_count + concept.down_count
        breadth_score = (
            concept.up_count / breadth_total * 100
            if breadth_total > 0 else 0.0
        )
        ladder_score = min(100.0, (
            8 * tiers["first_board"]
            + 18 * tiers["second_board"]
            + 28 * tiers["three_plus_board"]
            + 15 * sum(count > 0 for count in tiers.values())
        ))
        persistence_count = int(1 <= concept.hot_rank <= 10) + sum(
            1 <= ranks_by_date.get(session, {}).get(concept.name, 11) <= 10
            for session in prior_session_dates
        )
        activity_score = (
            _percentile_score(concept.pct, pct_values)
            + _percentile_score(concept.turnover_yi, turnover_values)
        ) / 2
        score = round(
            ladder_score * 0.35
            + breadth_score * 0.25
            + persistence_count * 20 * 0.25
            + activity_score * 0.15,
            2,
        )
        entries.append(MarketLineEntry(
            name=concept.name,
            code=concept.code,
            source_rank=concept.hot_rank,
            score=score,
            label="观察",
            rank=1,
            pct=concept.pct,
            turnover_yi=concept.turnover_yi,
            up_count=concept.up_count,
            down_count=concept.down_count,
            breadth_score=round(breadth_score, 2),
            persistence_count=persistence_count,
            ladder_score=round(ladder_score, 2),
            activity_score=round(activity_score, 2),
            ladder_tiers=tiers,
            known_bar_count=known_bars,
            eligible_small_cap_count=eligible_members,
            eligible_member_symbols=eligible_symbols,
            members=members,
        ))

    entries.sort(key=lambda item: (-item.score, -item.pct, -item.turnover_yi, item.name))
    ranked: list[MarketLineEntry] = []
    for rank, entry in enumerate(entries, 1):
        if (
            rank <= 3
            and entry.persistence_count >= 3
            and entry.breadth_score > 50
            and sum(entry.ladder_tiers.values()) >= 2
        ):
            label: Literal["持续主线", "主线候选", "快速轮动", "观察"] = "持续主线"
        elif rank <= 3 and entry.score >= 60 and entry.persistence_count >= 2:
            label = "主线候选"
        elif rank <= 3 and entry.score >= 60 and entry.persistence_count <= 1:
            label = "快速轮动"
        else:
            label = "观察"
        ranked.append(entry.model_copy(update={"rank": rank, "label": label}))

    return MarketLineSnapshot(
        status="fresh",
        as_of_date=as_of_date,
        generated_at=generated_at,
        source="同花顺",
        market_environment=market_environment,
        hot_concept_ranks=hot_ranks,
        hot_rank_basis="concept_gain_rank",
        concept_acquired_at=concept_acquired_at,
        lines=ranked[:MAX_LINES],
        evidence_lines=ranked,
    )


def _percentile_score(value: float, values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(candidate <= value for candidate in values) / len(values) * 100


def _market_session_dates(
    small_cap_rows: Sequence[Mapping[str, object]],
    as_of_date: date,
) -> list[date]:
    sessions: set[date] = set()
    for row in small_cap_rows:
        bars = row.get("bars")
        if not isinstance(bars, Sequence) or isinstance(bars, (str, bytes)):
            continue
        for bar in bars:
            if not isinstance(bar, Mapping):
                continue
            bar_date = _bar_date(bar.get("date"))
            if bar_date is not None and bar_date <= as_of_date:
                sessions.add(bar_date)
    if as_of_date not in sessions:
        sessions.add(as_of_date)
    return sorted(sessions)


def _bar_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
