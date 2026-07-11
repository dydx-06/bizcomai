import glob
import io
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.categorizer import SemanticCategorizer
from app.embeddings import HashingEmbedder
from app.scheme_matcher import SchemeMatcher


@pytest.fixture
def client(embedder):
    """Inject fakes onto app.state and mark it configured, so the lifespan hook
    does not load a real model or wire up Groq."""
    app = main_module.app
    app.state.embedder = embedder
    app.state.categorizer = SemanticCategorizer(embedder=embedder, llm_fn=None)
    app.state.matcher = SchemeMatcher(embedder=embedder)
    app.state.configured = True
    with TestClient(app) as c:
        yield c
    app.state.configured = False


def test_startup_does_not_clobber_injected_dependencies(embedder):
    """Regression. With module-level globals and an @on_event('startup') hook,
    startup overwrote the test's fakes. If GROQ_API_KEY were ever set in CI,
    these tests would silently begin calling the live API."""
    app = main_module.app
    sentinel = SemanticCategorizer(embedder=embedder, llm_fn=None)
    app.state.embedder = embedder
    app.state.categorizer = sentinel
    app.state.matcher = SchemeMatcher(embedder=embedder)
    app.state.configured = True
    try:
        with TestClient(app):
            assert app.state.categorizer is sentinel
    finally:
        app.state.configured = False


def test_llm_tier_reported_disabled_when_no_llm_injected(client):
    assert client.get("/health").json()["llm_tier_enabled"] is False


PROFILE = json.dumps(
    {
        "sector": "Manufacturing",
        "is_new_business": False,
        "udyam_registered": True,
        "needs_tech_upgrade": True,
        "current_bank_balance_inr": 500000,
    }
)

GOOD_CSV = (
    "Date,Description,Amount\n"
    "2024-01-05,RAZORPAY SETTLEMENT,50000\n"
    "2024-02-08,GST CHALLAN CBIC,-12000\n"
)


def post(client, csv_text, profile=PROFILE, need_text=""):
    return client.post(
        "/api/analyze",
        files={"file": ("statement.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        data={"profile_data": profile, "need_text": need_text},
    )


def test_health_reports_embedder_and_llm_state(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["embedder"] == "HashingEmbedder"


def test_happy_path_returns_200_and_full_payload(client):
    body = post(client, GOOD_CSV).json()
    assert body["status"] == "success"
    assert body["financial_health"]["summary"]["total_inflow"] == 50000
    assert body["eligible_schemes"]


def test_need_text_is_threaded_through_to_scheme_ranking(client):
    body = post(client, GOOD_CSV, need_text="subsidy to buy new machinery").json()
    assert any(s["semantic_score"] > 0 for s in body["eligible_schemes"])


# --- Error handling ---------------------------------------------------------

def test_malformed_profile_json_returns_400(client):
    r = post(client, GOOD_CSV, profile="{not json")
    assert r.status_code == 400
    assert "not valid JSON" in r.json()["error"]


def test_missing_amount_column_returns_400_not_500(client):
    """A bad upload is the user's problem to fix, so it must not be a 500."""
    r = post(client, "Date,Description\n2024-01-01,foo\n")
    assert r.status_code == 400
    assert "amount" in r.json()["error"].lower()


def test_empty_csv_returns_400(client):
    r = post(client, "Date,Description,Amount\n")
    assert r.status_code == 400


def test_garbage_upload_returns_400(client):
    r = post(client, "\x00\x01 not a csv at all")
    assert r.status_code == 400


# --- Temp file hygiene (regression) -----------------------------------------

def _temp_csvs():
    return set(glob.glob(str(Path(tempfile.gettempdir()) / "*.csv")))


def test_temp_file_removed_on_success(client):
    before = _temp_csvs()
    post(client, GOOD_CSV)
    assert _temp_csvs() - before == set()


def test_temp_file_removed_even_when_parsing_fails(client):
    """Original code called os.remove() only on the success path, so every bad
    upload leaked a file into /tmp."""
    before = _temp_csvs()
    r = post(client, "Date,Description\n2024-01-01,foo\n")
    assert r.status_code == 400
    assert _temp_csvs() - before == set()
