"""Shared fixtures.

Every fixture here is offline and deterministic. No test in this suite makes a
network call, so the suite runs in CI, on a plane, and on a grader's laptop.
"""
import socket

import pytest
import os
os.environ["HF_HUB_OFFLINE"] = "1"
from app.categorizer import SemanticCategorizer
from app.embeddings import HashingEmbedder
from app.scheme_matcher import SchemeMatcher
from app.embeddings import SentenceTransformerEmbedder

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket
    original_connect = socket.socket.connect

    def _blocked(self, address, *args, **kwargs):
        # Allow internal asyncio/TestClient connections on Windows
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1", "localhost"):
            return original_connect(self, address, *args, **kwargs)

        raise RuntimeError(
            f"A test attempted a network connection to {address}. "
            "Unit tests must be offline: inject a fake via the `llm_fn` parameter instead."
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)
@pytest.fixture
def embedder():
    # Swapped from HashingEmbedder to the real Neural Network
    return SentenceTransformerEmbedder()


@pytest.fixture
def categorizer(embedder):
    """LLM tier disabled: tests must never depend on Groq."""
    return SemanticCategorizer(embedder=embedder, llm_fn=None)


@pytest.fixture
def matcher(embedder):
    return SchemeMatcher(embedder=embedder)


@pytest.fixture
def established_manufacturer():
    return {
        "business_id": "biz_402",
        "sector": "Manufacturing",
        "turnover_inr": 12_000_000,
        "is_new_business": False,
        "udyam_registered": True,
        "women_owned": False,
        "sc_st_owned": False,
        "rural_location": False,
        "needs_tech_upgrade": True,
        "has_overdue_receivables_45_days": True,
        "required_loan_inr": 8_000_000,
    }


@pytest.fixture
def new_woman_entrepreneur():
    return {
        "business_id": "biz_777",
        "sector": "Services",
        "turnover_inr": 0,
        "is_new_business": True,
        "udyam_registered": False,
        "women_owned": True,
        "sc_st_owned": False,
        "rural_location": True,
        "needs_tech_upgrade": False,
        "required_loan_inr": 400_000,
    }


@pytest.fixture
def signed_amount_csv(tmp_path):
    p = tmp_path / "signed.csv"
    p.write_text(
        "Date,Description,Amount\n"
        "2024-01-05,RAZORPAY SETTLEMENT,50000\n"
        "2024-01-08,GST CHALLAN CBIC,-12000\n"
        "2024-01-20,INDIAMART VENDOR PAYMENT,-30000\n"
        "2024-02-03,BAJAJ FINANCE EMI,-8000\n"
    )
    return str(p)


@pytest.fixture
def split_column_csv(tmp_path):
    """The format most Indian banks actually export."""
    p = tmp_path / "split.csv"
    p.write_text(
        "Txn Date,Narration,Withdrawal,Deposit\n"
        "05-01-2024,NEFT FROM CUSTOMER ACME LTD,,75000\n"
        "10-01-2024,BESCOM ELECTRICITY BILL,4500,\n"
        "15-01-2024,SALARY DISBURSEMENT JAN,60000,\n"
    )
    return str(p)
