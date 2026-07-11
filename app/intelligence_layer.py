import json
from parser import parse_bank_statement
from scheme_matcher import match_schemes


def run_financial_advisor_pipeline(statement_csv_path: str, base_profile: dict) -> dict:
    print(f"--- Step 1: Parsing Bank Statement ({statement_csv_path}) ---")
    transactions = parse_bank_statement(statement_csv_path)

    # Proactive Intelligence: Scan transactions to update the business profile automatically
    has_delayed_payments = False
    total_inflow = 0
    total_outflow = 0

    for txn in transactions:
        amount = txn["amount"]
        if amount > 0:
            total_inflow += amount
        else:
            total_outflow += abs(amount)

        # Real-world indicator: If a transaction description matches manual entries of old dues
        # or overdue tags, or if our cashflow rules flag a massive outstanding gap.
        # For the demo, let's trigger it if we find a customer receipt that's explicitly a pending clearance.
        if "overdue" in txn["description"].lower() or "delayed" in txn["description"].lower():
            has_delayed_payments = True

    # Dynamically inject insights discovered from the bank statement into the profile
    updated_profile = base_profile.copy()
    updated_profile["turnover_inr"] = total_inflow  # Annualize or use directly as captured revenue

    if has_delayed_payments:
        updated_profile["has_overdue_receivables_45_days"] = True
        print("[Insight Found]: Detected critical delayed payments in transaction history!")

    print("\n--- Step 2: Matching Government Schemes Based on Live Data ---")
    recommended_schemes = match_schemes(updated_profile)

    # Generate proactive cashflow alert for the frontend
    cash_alert = None
    if total_outflow > total_inflow:
        cash_alert = "CRITICAL ALERT: Your cash outflow exceeds inflow this month. Consider checking CGTMSE working capital loans."
    elif has_delayed_payments:
        cash_alert = "CASHFLOW ALERT: Outstanding invoices detected. Look at MSME Samadhaan to recover funds."

    return {
        "business_profile_analyzed": updated_profile,
        "cashflow_summary": {
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
            "net_cashflow": total_inflow - total_outflow
        },
        "proactive_alert": cash_alert,
        "eligible_schemes": recommended_schemes
    }


if __name__ == "__main__":
    # 1. Mock the user's static registration profile
    user_profile = {
        "business_id": "biz_402",
        "sector": "Manufacturing",
        "is_new_business": False,
        "udyam_registered": True,
        "women_owned": False,
        "sc_st_owned": False,
        "rural_location": False,
        "needs_tech_upgrade": True
    }

    # 2. Run the end-to-end flow
    # This will read your test_statement.csv, analyze cashflow, and recommend schemes
    output = run_financial_advisor_pipeline("../test_statement1.csv", user_profile)

    print("\n--- Final Pipeline Output ")
    print(json.dumps(output, indent=2))