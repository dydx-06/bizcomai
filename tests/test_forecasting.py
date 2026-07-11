import pytest

from app.forecasting import (
    calendar_span_days,
    detect_expense_clusters,
    generate_cashflow_forecast,
    parse_date,
)


def txn(date, amount, description="txn"):
    return {"date": date, "amount": amount, "description": description}


# --- Date parsing -----------------------------------------------------------

@pytest.mark.parametrize("s", ["2024-01-05", "05-01-2024", "05/01/2024", "05-Jan-2024"])
def test_parse_date_accepts_common_indian_formats(s):
    d = parse_date(s)
    assert d is not None and d.day == 5 and d.month == 1


def test_parse_date_returns_none_on_garbage():
    assert parse_date("not a date") is None


def test_calendar_span_is_inclusive():
    assert calendar_span_days([parse_date("2024-01-01"), parse_date("2024-01-31")]) == 31


# --- The burn-rate bug ------------------------------------------------------

def test_burn_rate_divides_by_calendar_span_not_distinct_expense_days():
    """Regression. Original divided 90000 by 3 distinct days -> 30000/day.
    Correct is 90000 over a 90-day span -> 1000/day."""
    txns = [
        txn("2024-01-01", -30000),
        txn("2024-02-01", -30000),
        txn("2024-03-30", -30000),
    ]
    f = generate_cashflow_forecast(txns, current_bank_balance=200000)
    assert f.days_analyzed == 90
    assert f.daily_burn_rate == pytest.approx(1000.0)


def test_healthy_business_is_not_flagged_critical():
    """The bug made this company look 30x more distressed than it was."""
    txns = [txn("2024-01-01", -30000), txn("2024-02-01", -30000), txn("2024-03-30", -30000)]
    f = generate_cashflow_forecast(txns, current_bank_balance=200000)
    assert f.severity == "healthy"
    assert f.runway_days_remaining == 200


def test_credits_do_not_reduce_the_burn_rate():
    """Burn is gross outflow, not net. A large credit must not mask the burn.
    Span Jan 1 -> Jan 11 is 11 days inclusive, so 10000/11."""
    txns = [txn("2024-01-01", -10000), txn("2024-01-11", 500000)]
    f = generate_cashflow_forecast(txns, 100000)
    assert f.days_analyzed == 11
    assert f.daily_burn_rate == pytest.approx(10000 / 11, rel=1e-3)


# --- Severity thresholds ----------------------------------------------------

def test_zero_outflow_is_healthy_with_max_runway():
    f = generate_cashflow_forecast([txn("2024-01-01", 5000)], 10000)
    assert f.severity == "healthy"
    assert f.runway_days_remaining == 999
    assert f.daily_burn_rate == 0


def test_empty_transaction_list_is_healthy():
    assert generate_cashflow_forecast([], 10000).severity == "healthy"


def test_critical_when_runway_under_30_days():
    txns = [txn("2024-01-01", -1000), txn("2024-01-10", -1000)]  # 2000/10d = 200/day
    f = generate_cashflow_forecast(txns, 2000)  # 10 days
    assert f.severity == "critical"
    assert "CRITICAL" in f.forecast_alert


def test_warning_between_30_and_90_days():
    txns = [txn("2024-01-01", -1000), txn("2024-01-10", -1000)]  # 200/day
    f = generate_cashflow_forecast(txns, 12000)  # 60 days
    assert f.severity == "warning"
    assert f.runway_days_remaining == 60


def test_healthy_above_90_days():
    txns = [txn("2024-01-01", -1000), txn("2024-01-10", -1000)]
    assert generate_cashflow_forecast(txns, 40000).severity == "healthy"


def test_runway_is_clamped_to_max():
    txns = [txn("2024-01-01", -1), txn("2024-12-31", -1)]
    assert generate_cashflow_forecast(txns, 10**12).runway_days_remaining == 999


def test_zero_balance_gives_zero_runway_and_critical():
    txns = [txn("2024-01-01", -1000), txn("2024-01-10", -1000)]
    f = generate_cashflow_forecast(txns, 0)
    assert f.runway_days_remaining == 0
    assert f.severity == "critical"


def test_unparseable_dates_report_unknown_rather_than_guessing():
    f = generate_cashflow_forecast([txn("garbage", -1000)], 10000)
    assert f.severity == "unknown"
    assert f.daily_burn_rate == 0


# --- Expense clustering -----------------------------------------------------

def test_cluster_alert_fires_when_large_payments_share_a_week():
    txns = [
        txn("2024-01-02", -100000, "supplier A"),
        txn("2024-01-04", -90000, "supplier B"),
        txn("2024-03-15", -80000, "supplier C"),
        txn("2024-02-01", -500, "tea"),
    ]
    alerts = detect_expense_clusters(txns)
    assert len(alerts) == 1
    assert "CASH GAP RISK" in alerts[0]
    assert "190,000" in alerts[0]


def test_no_cluster_alert_when_large_payments_are_spread_out():
    txns = [
        txn("2024-01-02", -100000),
        txn("2024-03-04", -90000),
        txn("2024-06-15", -80000),
    ]
    assert detect_expense_clusters(txns) == []


def test_cluster_detection_ignores_credits():
    txns = [txn("2024-01-02", 100000), txn("2024-01-03", 90000), txn("2024-01-04", 80000)]
    assert detect_expense_clusters(txns) == []


def test_cluster_detection_needs_enough_debits():
    assert detect_expense_clusters([txn("2024-01-02", -100)]) == []


def test_cluster_alerts_are_attached_to_the_forecast():
    txns = [txn("2024-01-02", -100000), txn("2024-01-04", -90000), txn("2024-01-05", -80000)]
    assert generate_cashflow_forecast(txns, 1_000_000).cluster_alerts
