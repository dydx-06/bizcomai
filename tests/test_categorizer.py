import pytest

from app.categorizer import (
    ALLOWED_CATEGORIES,
    SemanticCategorizer,
    _sign_allows,
)
from app.embeddings import HashingEmbedder, StubEmbedder


# --- Tier 1: rules ----------------------------------------------------------

@pytest.mark.parametrize(
    "description,amount,expected",
    [
        ("IndiaMART vendor payment", -5000, "supplier_payment"),
        ("GST CHALLAN CBIC", -12000, "gst_payment"),
        ("BAJAJ FINANCE EMI", -8000, "loan_emi"),
        ("BESCOM ELECTRICITY", -2000, "utility"),
        ("RAZORPAY SETTLEMENT", 50000, "customer_receipt"),
        ("MONTHLY SALARY PAYOUT", -60000, "salary"),
    ],
)
def test_rule_tier_matches_known_keywords(categorizer, description, amount, expected):
    result = categorizer.categorize(description, amount)
    assert result.category == expected
    assert result.tier == "rule"
    assert result.confidence == 1.0


def test_rule_tier_is_case_insensitive(categorizer):
    assert categorizer.categorize("indiamart payment", -100).category == "supplier_payment"
    assert categorizer.categorize("INDIAMART PAYMENT", -100).category == "supplier_payment"


# --- Substring false positives (regression) ---------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "QUARTERLY TAX REMITTANCE TO GOVERNMENT",  # r-EMI-ttance
        "INSURANCE PREMIUM DEBIT",                  # pr-EMI-um
        "PURCHASE OF CHEMICALS FOR PLANT",          # ch-EMI-cals
    ],
)
def test_short_keyword_emi_does_not_match_inside_longer_words(categorizer, description):
    """'emi' is a substring of remittance, premium and chemicals. Word-boundary
    matching is required or all three get tagged as loan EMIs."""
    assert categorizer.categorize(description, -5000).category != "loan_emi"


def test_emi_still_matches_as_a_standalone_word(categorizer):
    assert categorizer.categorize("BAJAJ EMI DEBIT", -5000).category == "loan_emi"


def test_gst_keyword_does_not_match_inside_a_longer_token(categorizer):
    """'gst' is 3 chars, so it needs a boundary too."""
    r = categorizer.categorize("PAYMENT TO GSTAAD TRAVELS PVT LTD", -5000)
    assert r.category != "gst_payment"


# --- Sign constraints -------------------------------------------------------

def test_sign_allows_blocks_credit_only_category_on_debit():
    assert not _sign_allows("customer_receipt", -500)


def test_sign_allows_blocks_debit_only_category_on_credit():
    assert not _sign_allows("gst_payment", 500)


def test_razorpay_credit_is_receipt_but_debit_is_not(categorizer):
    """Razorpay is a rule keyword for customer_receipt. On a debit it must not fire."""
    assert categorizer.categorize("RAZORPAY SETTLEMENT", 5000).category == "customer_receipt"
    assert categorizer.categorize("RAZORPAY SETTLEMENT", -5000).category != "customer_receipt"


def test_no_result_ever_violates_sign_constraint(categorizer):
    for desc in ["random merchant xyz", "unknown vendor abc", "some payment"]:
        for amt in (-1000, 1000):
            r = categorizer.categorize(desc, amt)
            assert _sign_allows(r.category, amt), f"{r.category} illegal for amount {amt}"


# --- Tier 2: semantic -------------------------------------------------------

def test_semantic_tier_fires_when_stub_is_close_to_a_prototype():
    """A stub embedder makes the input a near-copy of the gst prototype."""
    proto = "goods and services tax challan payment"
    stub = StubEmbedder({proto: [1.0, 0.0, 0.0], "tax remittance to authorities": [0.99, 0.1, 0.0]})
    cat = SemanticCategorizer(
        embedder=stub,
        llm_fn=None,
        prototypes={"gst_payment": [proto]},
        rules={},
    )
    result = cat.categorize("tax remittance to authorities", -5000)
    assert result.category == "gst_payment"
    assert result.tier == "semantic"
    assert result.confidence > 0.9


def test_semantic_tier_declines_below_floor():
    """Similarity beneath the floor must not be reported as a match."""
    stub = StubEmbedder({"proto text": [1.0, 0.0], "totally unrelated": [0.0, 1.0]})
    cat = SemanticCategorizer(
        embedder=stub, llm_fn=None, prototypes={"gst_payment": ["proto text"]}, rules={}
    )
    result = cat.categorize("totally unrelated", -100)
    assert result.tier == "fallback"
    assert result.category == "uncategorized_expense"


def test_semantic_tier_declines_when_margin_too_thin():
    """Two categories nearly tied -> escalate rather than guess."""
    stub = StubEmbedder(
        {"a proto": [1.0, 0.0], "b proto": [0.999, 0.045], "query": [1.0, 0.0]}
    )
    cat = SemanticCategorizer(
        embedder=stub,
        llm_fn=None,
        prototypes={"gst_payment": ["a proto"], "loan_emi": ["b proto"]},
        rules={},
        margin_floor=0.05,
    )
    assert cat.categorize("query", -100).tier == "fallback"


# --- Tier 3: LLM ------------------------------------------------------------

def test_llm_tier_is_used_when_earlier_tiers_miss():
    calls = []

    def fake_llm(desc, amt):
        calls.append((desc, amt))
        return "office_expense"

    cat = SemanticCategorizer(
        embedder=HashingEmbedder(), llm_fn=fake_llm, prototypes={}, rules={}
    )
    result = cat.categorize("zzz unmatched merchant", -900)
    assert result.category == "office_expense"
    assert result.tier == "llm"
    assert len(calls) == 1


def test_llm_hallucinated_category_is_rejected():
    cat = SemanticCategorizer(
        embedder=HashingEmbedder(), llm_fn=lambda d, a: "crypto_gambling", prototypes={}, rules={}
    )
    result = cat.categorize("mystery txn", -500)
    assert result.category == "uncategorized_expense"
    assert result.tier == "fallback"


def test_llm_returning_sign_incompatible_category_is_rejected():
    """LLM says customer_receipt on a debit. Must be refused."""
    cat = SemanticCategorizer(
        embedder=HashingEmbedder(), llm_fn=lambda d, a: "customer_receipt", prototypes={}, rules={}
    )
    result = cat.categorize("mystery txn", -500)
    assert result.category == "uncategorized_expense"


def test_llm_exception_degrades_gracefully():
    def boom(desc, amt):
        raise ConnectionError("groq down")

    cat = SemanticCategorizer(embedder=HashingEmbedder(), llm_fn=boom, prototypes={}, rules={})
    result = cat.categorize("mystery txn", 500)
    assert result.category == "uncategorized_income"
    assert result.tier == "fallback"
    assert "groq down" in result.reason


def test_llm_is_never_called_when_rule_tier_hits():
    def should_not_run(desc, amt):
        raise AssertionError("LLM must not be called when a rule matches")

    cat = SemanticCategorizer(embedder=HashingEmbedder(), llm_fn=should_not_run)
    assert cat.categorize("GST CHALLAN", -100).tier == "rule"


# --- Caching and edges ------------------------------------------------------

def test_repeated_description_hits_cache_and_calls_llm_once():
    calls = []
    cat = SemanticCategorizer(
        embedder=HashingEmbedder(),
        llm_fn=lambda d, a: (calls.append(d), "office_expense")[1],
        prototypes={},
        rules={},
    )
    for _ in range(5):
        cat.categorize("repeated mystery merchant", -100)
    assert len(calls) == 1


def test_cache_key_separates_debit_from_credit():
    cat = SemanticCategorizer(embedder=HashingEmbedder(), llm_fn=None, prototypes={}, rules={})
    assert cat.categorize("ambiguous", -100).category == "uncategorized_expense"
    assert cat.categorize("ambiguous", 100).category == "uncategorized_income"


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_empty_description_falls_back_without_crashing(categorizer, bad):
    assert categorizer.categorize(bad, -100).category == "uncategorized_expense"


def test_every_returned_category_is_in_the_allowed_list(categorizer):
    samples = ["GST CHALLAN", "unknown thing", "", "RAZORPAY", "\u0906\u092f\u0915\u0930 \u092d\u0941\u0917\u0924\u093e\u0928"]
    for s in samples:
        for amt in (-100, 100):
            assert categorizer.categorize(s, amt).category in ALLOWED_CATEGORIES


def test_categorize_many_preserves_order(categorizer):
    rows = [("GST CHALLAN", -1), ("RAZORPAY", 1), ("BESCOM", -1)]
    cats = [r.category for r in categorizer.categorize_many(rows)]
    assert cats == ["gst_payment", "customer_receipt", "utility"]


def test_network_guard_is_active():
    """Meta-test: proves the autouse offline guard in conftest actually fires,
    so 'no network calls' is enforced rather than merely intended."""
    import socket

    with pytest.raises(RuntimeError, match="offline"):
        socket.socket().connect(("1.1.1.1", 80))
