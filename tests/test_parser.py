import pandas as pd
import pytest

from app.parser import (
    StatementParseError,
    _to_float,
    parse_bank_statement,
    parse_dataframe,
)


# --- Amount coercion --------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        (1000, 1000.0),
        (-250.5, -250.5),
        ("1,20,000.00", 120000.0),
        ("\u20b95,000", 5000.0),
        ("Rs. 2,500", 2500.0),
        ("5000 Dr", -5000.0),
        ("5000 Cr", 5000.0),
        ("(1500)", -1500.0),
        ("", 0.0),
    ],
)
def test_to_float_handles_indian_formats(raw, expected):
    assert _to_float(raw) == pytest.approx(expected)


def test_to_float_raises_on_garbage():
    with pytest.raises(StatementParseError):
        _to_float("not a number")


# --- Signed amount column ---------------------------------------------------

def test_signed_amount_csv_parses_and_signs_correctly(signed_amount_csv, categorizer):
    txns = parse_bank_statement(signed_amount_csv, categorizer)
    assert len(txns) == 4
    assert txns[0].type == "credit" and txns[0].amount == 50000
    assert txns[1].type == "debit" and txns[1].amount == -12000


def test_transaction_ids_are_unique(signed_amount_csv, categorizer):
    txns = parse_bank_statement(signed_amount_csv, categorizer)
    assert len({t.transaction_id for t in txns}) == len(txns)


# --- Split withdrawal/deposit columns (the original bug) --------------------

def test_split_columns_assign_correct_signs(split_column_csv, categorizer):
    """Original code mapped withdrawal AND deposit onto 'amount'; one silently won."""
    txns = parse_bank_statement(split_column_csv, categorizer)
    assert len(txns) == 3
    by_desc = {t.description: t for t in txns}
    assert by_desc["NEFT FROM CUSTOMER ACME LTD"].amount == 75000
    assert by_desc["BESCOM ELECTRICITY BILL"].amount == -4500
    assert by_desc["SALARY DISBURSEMENT JAN"].amount == -60000


def test_split_columns_produce_correct_categories(split_column_csv, categorizer):
    txns = parse_bank_statement(split_column_csv, categorizer)
    by_desc = {t.description: t.category for t in txns}
    assert by_desc["BESCOM ELECTRICITY BILL"] == "utility"
    assert by_desc["SALARY DISBURSEMENT JAN"] == "salary"


# --- Column inference -------------------------------------------------------

@pytest.mark.parametrize("desc_header", ["Description", "Particulars", "Narration", "Remarks"])
def test_description_column_aliases_are_recognized(desc_header, categorizer):
    df = pd.DataFrame({"Date": ["2024-01-01"], desc_header: ["GST CHALLAN"], "Amount": [-100]})
    txns = parse_dataframe(df, categorizer)
    assert txns[0].description == "GST CHALLAN"


def test_headers_are_whitespace_and_case_normalized(categorizer):
    df = pd.DataFrame({"  DATE ": ["2024-01-01"], " Narration": ["GST"], "AMOUNT  ": [-100]})
    assert len(parse_dataframe(df, categorizer)) == 1


# --- Error paths ------------------------------------------------------------

def test_empty_dataframe_raises(categorizer):
    with pytest.raises(StatementParseError, match="empty"):
        parse_dataframe(pd.DataFrame(), categorizer)


def test_missing_amount_column_raises_and_names_it(categorizer):
    df = pd.DataFrame({"Date": ["2024-01-01"], "Description": ["x"]})
    with pytest.raises(StatementParseError, match="amount"):
        parse_dataframe(df, categorizer)


def test_missing_date_column_raises(categorizer):
    df = pd.DataFrame({"Description": ["x"], "Amount": [-100]})
    with pytest.raises(StatementParseError, match="date"):
        parse_dataframe(df, categorizer)


def test_missing_file_raises_parse_error(categorizer):
    with pytest.raises(StatementParseError, match="not found"):
        parse_bank_statement("/nonexistent/path.csv", categorizer)


def test_rows_with_null_or_zero_amount_are_skipped(categorizer):
    df = pd.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "Description": ["GST", "blank row", "BESCOM"],
            "Amount": [-100, None, -50],
        }
    )
    assert len(parse_dataframe(df, categorizer)) == 2


def test_statement_with_no_usable_rows_raises(categorizer):
    df = pd.DataFrame({"Date": ["2024-01-01"], "Description": ["x"], "Amount": [None]})
    with pytest.raises(StatementParseError, match="No usable transactions"):
        parse_dataframe(df, categorizer)


def test_null_description_does_not_crash(categorizer):
    df = pd.DataFrame({"Date": ["2024-01-01"], "Description": [None], "Amount": [-100]})
    txns = parse_dataframe(df, categorizer)
    assert txns[0].category == "uncategorized_expense"


def test_parser_never_calls_the_llm_in_tests(categorizer, signed_amount_csv):
    """categorizer fixture has llm_fn=None; assert no tier is 'llm'."""
    txns = parse_bank_statement(signed_amount_csv, categorizer)
    assert all(t.category_tier != "llm" for t in txns)
