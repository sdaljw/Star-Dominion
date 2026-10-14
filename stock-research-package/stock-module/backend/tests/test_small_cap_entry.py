import importlib

import pytest


def factors(**extra):
    return {"rule_version": 4, "shortlist_qualified": True, "alert_active": True,
            "confirmation_date": "2026-09-10", "confirmation_age_days": 0,
            "confirmation_sector_status": "confirmed", "confirmation_sector_date": "2026-09-10",
            "confirmation_hot_theme_status": "confirmed", "confirmation_hot_theme_date": "2026-09-10",
            "confirmation_hot_theme_rank": 3, "confirmation_hot_theme_basis": "concept_gain_rank", **extra}


def gate(row):
    module = importlib.import_module("app.domain.small_cap_entry")
    return module.build_small_cap_entry_gate(row)


def test_entry_requires_active_v4_plus_same_date_hot_sector():
    assert gate(factors())["entry_eligible"] is True
    assert gate(factors())["entry_gate_status"] == "eligible"
    assert gate(factors())["entry_gate_version"] == 3
    assert gate(factors())["entry_basis"] == "both"


@pytest.mark.parametrize("extra,status", [
    ({"alert_active": False}, "waiting_signal"),
    ({"shortlist_qualified": False}, "waiting_signal"),
    ({"confirmation_age_days": 3}, "waiting_signal"),
    ({"rule_version": 3}, "waiting_signal"),
    ({"confirmation_sector_status": "unavailable", "confirmation_hot_theme_status": "unavailable"}, "evidence_unavailable"),
    ({"confirmation_sector_status": "not_confirmed", "confirmation_hot_theme_status": "not_confirmed"}, "evidence_not_confirmed"),
    ({"confirmation_sector_status": "unavailable", "confirmation_hot_theme_date": "2026-09-11"}, "invalid_evidence"),
    ({"confirmation_hot_theme_status": "unavailable", "confirmation_sector_date": "2026-09-08"}, "invalid_evidence"),
    ({"confirmation_sector_status": "unavailable", "confirmation_hot_theme_basis": "unavailable"}, "invalid_evidence"),
    ({"confirmation_sector_status": "unavailable", "confirmation_hot_theme_rank": 21}, "invalid_evidence"),
])
def test_failed_or_unknown_conditions_do_not_become_entries(extra, status):
    result = gate(factors(**extra))
    assert result["entry_eligible"] is False
    assert result["entry_gate_status"] == status
    assert result["entry_gate_reason"]


def test_legacy_or_empty_cache_has_no_entry_qualification():
    assert gate({})["entry_eligible"] is False


@pytest.mark.parametrize("unused", ["unavailable", "not_confirmed"])
def test_hot_only_top_twenty_is_eligible_without_sector_evidence(unused):
    result = gate(factors(confirmation_sector_status=unused, confirmation_hot_theme_rank=20))
    assert result["entry_eligible"] is True
    assert result["entry_basis"] == "hot_theme_only"


@pytest.mark.parametrize("unused", ["unavailable", "not_confirmed"])
def test_sector_only_is_eligible_without_hot_theme_evidence(unused):
    result = gate(factors(confirmation_hot_theme_status=unused))
    assert result["entry_eligible"] is True
    assert result["entry_basis"] == "sector_only"


@pytest.mark.parametrize("extra,basis", [
    ({"confirmation_hot_theme_date": "2026-09-11"}, "sector_only"),
    ({"confirmation_hot_theme_rank": 21}, "sector_only"),
    ({"confirmation_sector_date": "2026-09-08"}, "hot_theme_only"),
])
def test_invalid_unused_branch_does_not_veto_a_valid_branch(extra, basis):
    result = gate(factors(**extra))
    assert result["entry_eligible"] is True
    assert result["entry_basis"] == basis
