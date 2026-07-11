"""Cashflow forecasting.

Bug fixed from the original
---------------------------
Burn rate was `total_outflow / len(distinct_expense_days)`. If a business spends
on 12 days out of a 90-day statement, that overstates daily burn by 7.5x and the
runway alert screams CRITICAL at a perfectly healthy company. Burn must be
divided by the *calendar span* of the statement, not by the number of days that
happened to have a transaction.

Added
-----
`detect_expense_clusters` implements the alert promised in the project pitch:
"your three largest supplier payments all fall in the same week."
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y")

CRITICAL_DAYS = 30
WARNING_DAYS = 90
MAX_RUNWAY = 999


@dataclass
class Forecast:
    daily_burn_rate: float
    runway_days_remaining: int
    forecast_alert: str
    severity: str  # "critical" | "warning" | "healthy" | "unknown"
    days_analyzed: int
    cluster_alerts: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_date(value: str) -> Optional[datetime]:
    s = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _amount(txn: Any) -> float:
    return float(txn["amount"] if isinstance(txn, dict) else txn.amount)


def _date(txn: Any) -> str:
    return str(txn["date"] if isinstance(txn, dict) else txn.date)


def _description(txn: Any) -> str:
    return str(txn["description"] if isinstance(txn, dict) else txn.description)


def calendar_span_days(dates: Sequence[datetime]) -> int:
    """Inclusive day count between the earliest and latest date."""
    if not dates:
        return 0
    return (max(dates) - min(dates)).days + 1


def detect_expense_clusters(transactions: Sequence[Any], top_n: int = 3) -> List[str]:
    """Flag when the largest outflows bunch into a single ISO week."""
    debits = [t for t in transactions if _amount(t) < 0]
    dated = [(parse_date(_date(t)), t) for t in debits]
    dated = [(d, t) for d, t in dated if d is not None]
    if len(dated) < top_n:
        return []

    dated.sort(key=lambda dt: abs(_amount(dt[1])), reverse=True)
    largest = dated[:top_n]

    by_week: Dict[tuple, list] = defaultdict(list)
    for d, t in largest:
        by_week[(d.isocalendar()[0], d.isocalendar()[1])].append(t)

    alerts = []
    for (year, week), group in by_week.items():
        if len(group) >= 2:
            total = sum(abs(_amount(t)) for t in group)
            alerts.append(
                f"CASH GAP RISK: {len(group)} of your {top_n} largest payments "
                f"(\u20b9{total:,.0f} total) fall in the same week (week {week}, {year})."
            )
    return alerts


def generate_cashflow_forecast(transactions: Sequence[Any], current_bank_balance: float) -> Forecast:
    debits = [t for t in transactions if _amount(t) < 0]
    total_outflow = sum(abs(_amount(t)) for t in debits)

    parsed = [parse_date(_date(t)) for t in transactions]
    valid_dates = [d for d in parsed if d is not None]

    if total_outflow == 0:
        return Forecast(0.0, MAX_RUNWAY, "Cashflow is stable. No immediate burn detected.", "healthy", 0, [])

    span = calendar_span_days(valid_dates)
    if span == 0:
        # Dates unparseable. Be honest rather than inventing a burn rate.
        return Forecast(
            0.0, MAX_RUNWAY,
            "Could not read transaction dates, so cash runway could not be estimated.",
            "unknown", 0, [],
        )

    daily_burn = total_outflow / span
    runway = int(current_bank_balance / daily_burn) if daily_burn > 0 else MAX_RUNWAY
    runway = max(0, min(runway, MAX_RUNWAY))
    clusters = detect_expense_clusters(transactions)

    if runway < CRITICAL_DAYS:
        severity = "critical"
        alert = (
            f"CRITICAL: at your current burn rate (\u20b9{daily_burn:,.2f}/day), you will run "
            f"out of cash in {runway} days. Emergency funding recommended."
        )
    elif runway < WARNING_DAYS:
        severity = "warning"
        alert = (
            f"WARNING: you have {runway} days of cash runway remaining. "
            "Start applying for working capital now."
        )
    else:
        severity = "healthy"
        alert = "HEALTHY: you have over 3 months of cash runway based on recent spending."

    return Forecast(round(daily_burn, 2), runway, alert, severity, span, clusters)
