import pytest

from app.parser import Transaction, parse_bank_statement
from app.pipeline import analyze, detect_overdue, enrich_profile, run_from_csv, summarize


def tx(desc, amount, date="2024-01-01", category="uncategorized_expense"):
    return Transaction("tx_0", date, desc, amount, "debit" if amount < 0 else "credit", category)


# --- Summary ----------------------------------------------------------------

def test_summarize_splits_inflow_and_outflow():
    s = summarize([tx("a", 1000), tx("b", -400)])
    assert s == {"total_inflow": 1000, "total_outflow": 400, "net_cashflow": 600}


def test_summarize_of_empty_list_is_all_zero():
    assert summarize([]) == {"total_inflow": 0, "total_outflow": 0, "net_cashflow": 0}


# --- Overdue detection ------------------------------------------------------

@pytest.mark.parametrize("desc", ["OVERDUE invoice", "delayed payment", "Outstanding dues", "pending clearance"])
def test_overdue_markers_detected_case_insensitively(desc):
    assert detect_overdue([tx(desc, 1000)])


def test_no_overdue_marker_returns_false():
    assert not detect_overdue([tx("regular payment", 1000)])


# --- Profile enrichment -----------------------------------------------------

def test_enrich_profile_sets_turnover_from_inflow():
    p = enrich_profile({"sector": "Manufacturing"}, [tx("sale", 5000), tx("cost", -2000)])
    assert p["turnover_inr"] == 5000


def test_enrich_profile_flags_overdue_receivables():
    p = enrich_profile({}, [tx("OVERDUE from customer", 5000)])
    assert p["has_overdue_receivables_45_days"] is True


def test_enrich_profile_does_not_mutate_the_input():
    base = {"sector": "Manufacturing"}
    enrich_profile(base, [tx("sale", 5000)])
    assert "turnover_inr" not in base


# --- analyze() --------------------------------------------------------------

def test_analyze_returns_the_full_contract(matcher):
    txns = [tx("RAZORPAY", 100000, "2024-01-01"), tx("BESCOM", -1000, "2024-02-01")]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 500000, matcher=matcher)
    for key in (
        "status",
        "business_profile_analyzed",
        "transactions",
        "financial_health",
        "proactive_alerts",
        "eligible_schemes",
        "categorization_tiers",
    ):
        assert key in out
    assert out["status"] == "success"


def test_analyze_surfaces_overdue_alert(matcher):
    txns = [tx("OVERDUE customer invoice", 100000, "2024-01-01")]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 500000, matcher=matcher)
    assert any("Samadhaan" in a for a in out["proactive_alerts"])


def test_overdue_transaction_unlocks_the_samadhaan_scheme(matcher):
    """The integration point that matters: statement data feeds scheme matching."""
    txns = [tx("OVERDUE customer invoice", 100000, "2024-01-01")]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 500000, matcher=matcher)
    assert any("Samadhaan" in s["scheme_name"] for s in out["eligible_schemes"])


def test_healthy_forecast_produces_no_runway_alert(matcher):
    txns = [tx("BESCOM", -100, "2024-01-01"), tx("BESCOM", -100, "2024-06-01")]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 10_000_000, matcher=matcher)
    assert not any("CRITICAL" in a or "WARNING" in a for a in out["proactive_alerts"])


def test_critical_forecast_produces_an_alert(matcher):
    txns = [tx("BESCOM", -5000, "2024-01-01"), tx("BESCOM", -5000, "2024-01-10")]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 1000, matcher=matcher)
    assert any("CRITICAL" in a for a in out["proactive_alerts"])


def test_categorization_tier_breakdown_counts_all_transactions(matcher):
    txns = [tx("a", 100), tx("b", -100)]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 5000, matcher=matcher)
    assert sum(out["categorization_tiers"].values()) == 2


def test_output_is_json_serializable(matcher):
    import json

    txns = [tx("RAZORPAY", 100000, "2024-01-01")]
    out = analyze(txns, {"sector": "Manufacturing", "is_new_business": False}, 5000, matcher=matcher)
    json.loads(json.dumps(out))  # must not raise


# --- Full CSV -> report -----------------------------------------------------

def test_run_from_csv_end_to_end(signed_amount_csv, categorizer, matcher):
    out = run_from_csv(
        signed_amount_csv,
        {"sector": "Manufacturing", "is_new_business": False, "udyam_registered": True, "needs_tech_upgrade": True},
        current_balance=500_000,
        categorizer=categorizer,
        matcher=matcher,
    )
    assert out["status"] == "success"
    assert out["financial_health"]["summary"]["total_inflow"] == 50000
    assert out["financial_health"]["summary"]["total_outflow"] == 50000
    assert out["business_profile_analyzed"]["turnover_inr"] == 50000
    assert len(out["transactions"]) == 4


def test_run_from_csv_with_split_columns(split_column_csv, categorizer, matcher):
    out = run_from_csv(
        split_column_csv,
        {"sector": "Manufacturing", "is_new_business": False},
        current_balance=500_000,
        categorizer=categorizer,
        matcher=matcher,
    )
    assert out["financial_health"]["summary"]["total_inflow"] == 75000
    assert out["financial_health"]["summary"]["total_outflow"] == 64500
