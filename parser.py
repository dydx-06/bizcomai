import pandas as pd
from typing import List, Dict

# Rule-based categorization engine
CATEGORY_RULES = {
    "supplier_payment": ["indiamart", "wholesale", "logistics", "metals"],
    "gst_payment": ["gst", "cbic", "tax"],
    "loan_emi": ["emi", "finance", "bajaj", "muthoot", "hdfc loan"],
    "utility": ["bescom", "mahavitaran", "jio", "airtel"],
    "customer_receipt": ["razorpay", "instamojo", "ccavenue", "neft-"]
}


def categorize_transaction(description: str, amount: float) -> str:
    desc_lower = str(description).lower()

    # Categorize based on keywords
    for category, keywords in CATEGORY_RULES.items():
        if any(keyword in desc_lower for keyword in keywords):
            return category

    # Fallback logic based on cashflow direction
    return "uncategorized_expense" if amount < 0 else "uncategorized_income"


def parse_bank_statement(file_path: str) -> List[Dict]:
    # Read the raw bank statement (assuming CSV for the MVP)
    df = pd.read_csv(file_path)

    # Standardize column names (Map these to whatever format your test CSV uses)
    df = df.rename(columns={
        "Txn Date": "date",
        "Description": "description",
        "Amount": "amount"
    })

    processed_transactions = []

    for index, row in df.iterrows():
        txn = {
            "transaction_id": f"tx_{index}",
            "date": row['date'],
            "description": row['description'],
            "amount": float(row['amount']),
            "type": "debit" if float(row['amount']) < 0 else "credit",
            "category": categorize_transaction(row['description'], float(row['amount']))
        }
        processed_transactions.append(txn)

    return processed_transactions


# Replace the bottom block in your code with this:
if __name__ == "__main__":
    # Run the parser and print the output beautifully
    import json
    results = parse_bank_statement("test_statement.csv")
    print(json.dumps(results, indent=2))