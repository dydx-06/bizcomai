"""Bank statement parsing.

Two changes from the original that matter:

1. `parse_bank_statement` returned either a list or an error dict, forcing every
   caller to `isinstance`-check. It now raises `StatementParseError`. Callers
   catch it once, at the API boundary.

2. Indian bank CSVs very often have *separate* Withdrawal and Deposit columns
   rather than one signed Amount column. The original `rename_map` mapped both
   onto "amount", so whichever came last silently won and half the transactions
   got the wrong sign. That is now handled explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import pandas as pd

from .categorizer import SemanticCategorizer


class StatementParseError(ValueError):
    """Raised when a statement cannot be understood. Message is user-facing."""


@dataclass
class Transaction:
    transaction_id: str
    date: str
    description: str
    amount: float
    type: str  # "debit" | "credit"
    category: str
    category_tier: str = "fallback"
    category_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DATE_HINTS = ("date", "txn date", "value date")
DESC_HINTS = ("description", "particulars", "narration", "remarks", "details")
AMOUNT_HINTS = ("amount", "amt")
DEBIT_HINTS = ("withdrawal", "debit")
CREDIT_HINTS = ("deposit", "credit")

# Two-letter abbreviations must match a whole token, never a substring.
# "description" contains "cr" (des-CR-iption); substring matching would silently
# select the description column as the credit column and then try to parse the
# narration text as a number.
DEBIT_EXACT = ("dr", "dr amt", "dr.")
CREDIT_EXACT = ("cr", "cr amt", "cr.")


def _tokens(col: str) -> set:
    return set(col.replace("/", " ").replace("_", " ").replace(".", " ").split())


def _find(columns: List[str], hints: tuple, exact: tuple = ()) -> Optional[str]:
    for col in columns:
        if any(h in col for h in hints):
            return col
    for col in columns:
        if _tokens(col) & set(exact):
            return col
    return None


def _to_float(value: Any) -> float:
    """Indian statements ship amounts like '1,20,000.00 Dr' or '₹5,000'."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("\u20b9", "").replace("Rs.", "").replace("Rs", "")
    negative = False
    upper = s.upper()
    for token in (" DR", "DR", "(", ")"):
        if token in upper:
            negative = negative or token.strip() in ("DR", "(")
    upper = upper.replace(" DR", "").replace("DR", "").replace(" CR", "").replace("CR", "")
    upper = upper.replace("(", "").replace(")", "").strip()
    if not upper:
        return 0.0
    try:
        val = float(upper)
    except ValueError as exc:
        raise StatementParseError(f"Could not read amount {value!r}") from exc
    return -abs(val) if negative else val


def _resolve_amount(row: pd.Series, amount_col, debit_col, credit_col) -> Optional[float]:
    """Signed amount. Debit is negative, credit positive.

    A single signed `amount` column is authoritative. Split withdrawal/deposit
    columns are only consulted when no such column exists.
    """
    if amount_col is None and (debit_col or credit_col):
        debit = _to_float(row[debit_col]) if debit_col and not pd.isna(row.get(debit_col)) else 0.0
        credit = _to_float(row[credit_col]) if credit_col and not pd.isna(row.get(credit_col)) else 0.0
        if debit == 0.0 and credit == 0.0:
            return None
        # A row is one or the other, never both.
        return -abs(debit) if debit != 0.0 else abs(credit)

    if amount_col is None or pd.isna(row.get(amount_col)):
        return None
    return _to_float(row[amount_col])


def parse_dataframe(df: pd.DataFrame, categorizer: SemanticCategorizer) -> List[Transaction]:
    if df.empty:
        raise StatementParseError("The uploaded bank statement is empty.")

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    cols = list(df.columns)

    date_col = _find(cols, DATE_HINTS)
    desc_col = _find(cols, DESC_HINTS)
    debit_col = _find(cols, DEBIT_HINTS, DEBIT_EXACT)
    credit_col = _find(cols, CREDIT_HINTS, CREDIT_EXACT)
    amount_col = _find(cols, AMOUNT_HINTS)

    missing = [
        name
        for name, col in (("date", date_col), ("description", desc_col))
        if col is None
    ]
    if amount_col is None and not (debit_col or credit_col):
        missing.append("amount (or withdrawal/deposit)")
    if missing:
        raise StatementParseError(
            f"Invalid file format. Missing critical column(s): {', '.join(missing)}."
        )

    transactions: List[Transaction] = []
    for index, row in df.iterrows():
        amount = _resolve_amount(row, amount_col, debit_col, credit_col)
        if amount is None or amount == 0.0:
            continue  # blank or zero-value row; skip silently

        description = str(row[desc_col]) if not pd.isna(row[desc_col]) else ""
        result = categorizer.categorize(description, amount)

        transactions.append(
            Transaction(
                transaction_id=f"tx_{index}",
                date=str(row[date_col]),
                description=description,
                amount=amount,
                type="debit" if amount < 0 else "credit",
                category=result.category,
                category_tier=result.tier,
                category_confidence=round(result.confidence, 4),
            )
        )

    if not transactions:
        raise StatementParseError("No usable transactions found in the statement.")
    return transactions


def parse_bank_statement(file_path: str, categorizer: Optional[SemanticCategorizer] = None) -> List[Transaction]:
    categorizer = categorizer or SemanticCategorizer()
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError as exc:
        raise StatementParseError(f"File not found: {file_path}") from exc
    except pd.errors.EmptyDataError as exc:
        raise StatementParseError("The uploaded bank statement is empty.") from exc
    except Exception as exc:
        raise StatementParseError(f"Could not read the file as CSV: {exc}") from exc
    return parse_dataframe(df, categorizer)
