"""End-to-end financial intelligence pipeline.

Previously this logic lived twice: once in `intelligence_layer.py` and again,
copy-pasted, inside the `/api/analyze` handler in `main.py`. Two copies drift.
This is the one copy; the API handler calls it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .categorizer import SemanticCategorizer
from .forecasting import generate_cashflow_forecast
from .parser import Transaction, parse_bank_statement
from .scheme_matcher import SchemeMatcher

OVERDUE_MARKERS = ("overdue", "delayed", "outstanding", "pending clearance")


def detect_overdue(transactions: Sequence[Transaction]) -> bool:
    return any(any(m in t.description.lower() for m in OVERDUE_MARKERS) for t in transactions)


def summarize(transactions: Sequence[Transaction]) -> Dict[str, float]:
    inflow = sum(t.amount for t in transactions if t.amount > 0)
    outflow = sum(abs(t.amount) for t in transactions if t.amount < 0)
    return {"total_inflow": inflow, "total_outflow": outflow, "net_cashflow": inflow - outflow}


def enrich_profile(base_profile: Dict, transactions: Sequence[Transaction]) -> Dict:
    """Fold what the bank statement reveals back into the business profile."""
    profile = dict(base_profile)
    profile["turnover_inr"] = summarize(transactions)["total_inflow"]
    if detect_overdue(transactions):
        profile["has_overdue_receivables_45_days"] = True
    return profile


def analyze(
    transactions: List[Transaction],
    base_profile: Dict,
    current_balance: float,
    need_text: str = "",
    matcher: Optional[SchemeMatcher] = None,
) -> Dict[str, Any]:
    matcher = matcher or SchemeMatcher()

    profile = enrich_profile(base_profile, transactions)
    summary = summarize(transactions)
    forecast = generate_cashflow_forecast(transactions, current_balance)
    schemes = matcher.match(profile, need_text)

    alerts: List[str] = []
    if forecast.severity in ("critical", "warning"):
        alerts.append(forecast.forecast_alert)
    alerts.extend(forecast.cluster_alerts)
    if profile.get("has_overdue_receivables_45_days"):
        alerts.append("Outstanding invoices detected. MSME Samadhaan can help recover these funds.")

    # Categorization tier breakdown -- useful evidence for the project report.
    tiers: Dict[str, int] = {}
    for t in transactions:
        tiers[t.category_tier] = tiers.get(t.category_tier, 0) + 1

    return {
        "status": "success",
        "business_profile_analyzed": profile,
        "transactions": [t.to_dict() for t in transactions],
        "financial_health": {"summary": summary, "forecasting": forecast.to_dict()},
        "proactive_alerts": alerts,
        "eligible_schemes": [s.to_dict() for s in schemes],
        "categorization_tiers": tiers,
    }


def run_from_csv(
    csv_path: str,
    base_profile: Dict,
    current_balance: float,
    need_text: str = "",
    categorizer: Optional[SemanticCategorizer] = None,
    matcher: Optional[SchemeMatcher] = None,
) -> Dict[str, Any]:
    transactions = parse_bank_statement(csv_path, categorizer or SemanticCategorizer())
    return analyze(transactions, base_profile, current_balance, need_text, matcher)
