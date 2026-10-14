"""Shared entry qualification; observed volume signals are not automatically buy candidates."""

from collections.abc import Mapping
from datetime import date

from app.domain.probe_sector import HOT_THEME_MAX_RANK


def build_small_cap_entry_gate(factors: Mapping[str, object]) -> dict[str, bool | str | int]:
    age = factors.get("confirmation_age_days")
    sector, hot = False, False
    if (factors.get("rule_version") != 4 or factors.get("shortlist_qualified") is not True
            or factors.get("alert_active") is not True or not isinstance(age, int)
            or isinstance(age, bool) or not 0 <= age <= 2):
        status, reason = "waiting_signal", "等待有效放量确认"
    else:
        signal_date = factors.get("confirmation_date")
        rank = factors.get("confirmation_hot_theme_rank")
        try:
            valid_date = isinstance(signal_date, str) and date.fromisoformat(signal_date).isoformat() == signal_date
        except ValueError:
            valid_date = False
        sector = (valid_date and factors.get("confirmation_sector_status") == "confirmed"
                  and factors.get("confirmation_sector_date") == signal_date)
        hot = (valid_date and factors.get("confirmation_hot_theme_status") == "confirmed"
               and factors.get("confirmation_hot_theme_date") == signal_date
               and factors.get("confirmation_hot_theme_basis") == "concept_gain_rank"
               and isinstance(rank, int) and not isinstance(rank, bool) and 1 <= rank <= HOT_THEME_MAX_RANK)
        if sector or hot:
            status = "eligible"
            reason = "板块联动与热门题材均命中" if sector and hot else (
                "仅同期板块联动" if sector else "仅同期热门题材前20")
        elif not valid_date or any(factors.get(key) == "confirmed" for key in (
                "confirmation_sector_status", "confirmation_hot_theme_status")):
            status, reason = "invalid_evidence", "同期题材证据日期或排序口径不完整"
        elif any(factors.get(key) != "not_confirmed" for key in (
                "confirmation_sector_status", "confirmation_hot_theme_status")):
            status, reason = "evidence_unavailable", "板块联动或热门题材证据待补"
        else:
            status, reason = "evidence_not_confirmed", "未命中板块联动或热门题材前20"
    basis = "both" if sector and hot else "sector_only" if sector else "hot_theme_only" if hot else "none"
    return {"entry_gate_version": 3, "entry_eligible": status == "eligible", "entry_basis": basis,
            "entry_sector_qualified": sector, "entry_hot_theme_qualified": hot,
            "entry_gate_status": status, "entry_gate_reason": reason}
