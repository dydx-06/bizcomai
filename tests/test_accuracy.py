"""Golden-set accuracy harness.

This is the file that turns "we wrote a classifier" into "we wrote a classifier
and measured it." It reports overall accuracy, a per-category breakdown, and how
much work each tier is doing -- all numbers you can put straight into the report.

Run just this file with output visible:

    pytest tests/test_accuracy.py -s -q
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent / "golden_transactions.csv"

# The rule + semantic tiers alone (no LLM) must clear this bar.
MIN_ACCURACY = 0.90


def load_golden():
    with GOLDEN.open() as fh:
        return [(r["description"], float(r["amount"]), r["expected_category"]) for r in csv.DictReader(fh)]


def test_golden_set_is_non_trivial():
    rows = load_golden()
    assert len(rows) >= 6
    assert len({r[2] for r in rows}) >= 6, "golden set should span at least 6 categories"


def test_offline_accuracy_meets_threshold(categorizer, capsys):
    rows = load_golden()
    correct = 0
    per_cat = defaultdict(lambda: [0, 0])  # category -> [correct, total]
    per_tier = defaultdict(int)
    failures = []

    for desc, amount, expected in rows:
        result = categorizer.categorize(desc, amount)
        per_tier[result.tier] += 1
        per_cat[expected][1] += 1
        if result.category == expected:
            correct += 1
            per_cat[expected][0] += 1
        else:
            failures.append((desc, expected, result.category, result.tier))

    accuracy = correct / len(rows)

    with capsys.disabled():
        print(f"\n\n  Categorization accuracy (rules + semantic, no LLM): {accuracy:.1%}")
        print(f"  {correct}/{len(rows)} correct\n")
        print("  Per-category:")
        for cat, (c, t) in sorted(per_cat.items()):
            print(f"    {cat:<22} {c}/{t}")
        print("\n  Resolved by tier:")
        for tier, n in sorted(per_tier.items(), key=lambda kv: -kv[1]):
            print(f"    {tier:<12} {n:>3}  ({n / len(rows):.0%})")
        if failures:
            print("\n  Misclassified:")
            for d, exp, got, tier in failures:
                print(f"    {d[:40]:<42} expected={exp} got={got} [{tier}]")
        print()

    assert accuracy >= MIN_ACCURACY, f"accuracy {accuracy:.1%} below {MIN_ACCURACY:.0%}"


def test_no_golden_row_needs_the_llm(categorizer):
    """If the rule + semantic tiers cover the golden set, production spends
    almost nothing on Groq. Any 'fallback' here is a gap to fix with a new
    prototype phrase, not with an API call."""
    unresolved = [
        d for d, a, _ in load_golden() if categorizer.categorize(d, a).tier == "fallback"
    ]
    assert not unresolved, f"these fell through to fallback: {unresolved}"


@pytest.mark.parametrize("desc,amount,expected", load_golden())
def test_each_golden_row_individually(categorizer, desc, amount, expected):
    """One test per row, so a regression names the exact transaction."""
    assert categorizer.categorize(desc, amount).category == expected


# --------------------------------------------------------------------------
# Measuring the SEMANTIC tier honestly.
#
# The easy golden set above is resolved 100% by the keyword rules, which means
# it says nothing about whether the embeddings work. To measure the semantic
# tier we must (a) use descriptions no keyword matches, and (b) disable the
# rule tier so it cannot answer on the semantic tier's behalf.
# --------------------------------------------------------------------------

GOLDEN_SEMANTIC = Path(__file__).parent / "golden_semantic.csv"
MIN_SEMANTIC_ACCURACY = 0.80


def load_semantic_golden():
    with GOLDEN_SEMANTIC.open() as fh:
        return [(r["description"], float(r["amount"]), r["expected_category"]) for r in csv.DictReader(fh)]


@pytest.fixture
def semantic_only(embedder):
    """Rules disabled, LLM disabled. Only embeddings can answer."""
    from app.categorizer import SemanticCategorizer

    return SemanticCategorizer(embedder=embedder, llm_fn=None, rules={})


def test_hard_golden_rows_are_not_solvable_by_keyword_rules(categorizer):
    """Guard the guard: if someone adds a keyword that trivially matches these,
    this test fails and the semantic benchmark stops being meaningful."""
    trivially_matched = [
        d for d, a, _ in load_semantic_golden() if categorizer.categorize(d, a).tier == "rule"
    ]
    assert not trivially_matched, f"these are solved by rules, so they don't test semantics: {trivially_matched}"


def test_semantic_tier_accuracy(semantic_only, capsys):
    rows = load_semantic_golden()
    correct, by_tier, failures = 0, defaultdict(int), []

    for desc, amount, expected in rows:
        r = semantic_only.categorize(desc, amount)
        by_tier[r.tier] += 1
        if r.category == expected:
            correct += 1
        else:
            failures.append((desc, expected, r.category, r.tier, r.confidence))

    accuracy = correct / len(rows)
    with capsys.disabled():
        print(f"\n\n  SEMANTIC-TIER-ONLY accuracy (rules + LLM disabled): {accuracy:.1%}")
        print(f"  {correct}/{len(rows)} correct")
        print(f"  tiers: {dict(by_tier)}")
        if failures:
            print("  Misses:")
            for d, exp, got, tier, conf in failures:
                print(f"    {d[:44]:<46} expected={exp:<20} got={got:<22} [{tier} {conf:.2f}]")
        print()

    assert accuracy >= MIN_SEMANTIC_ACCURACY, f"semantic accuracy {accuracy:.1%} below {MIN_SEMANTIC_ACCURACY:.0%}"


# --------------------------------------------------------------------------
# The limits of HashingEmbedder, stated honestly.
#
# The 100% above is real but narrow: those descriptions are paraphrases of the
# prototype phrases, and a character-trigram hasher matches surface form. On
# actual bank narration -- "UPI/9823/SHREE ENTERPRISES/PURCH" -- it scores 0%.
#
# That is FINE, and it is the reason the confidence floor exists: the hasher
# fails to `fallback` at 0.00 confidence rather than guessing. In production
# those rows escalate to the LLM tier.
#
# The tests below pin that contract down. If you swap in the real
# SentenceTransformerEmbedder, `test_hasher_cannot_read_real_bank_narration`
# is expected to fail -- and that failure is the signal the upgrade worked.
# --------------------------------------------------------------------------

REALISTIC_NARRATIONS = [
    ("UPI/9823/SHREE ENTERPRISES/PURCH", -22000, "supplier_payment"),
    ("ACH-D- TATA CAPITAL LTD-INSTL", -9100, "loan_emi"),
    ("IMPS/P2A/ACME CORP/INV4471", 55000, "customer_receipt"),
    ("MSEDCL BILL PMT 9812", -3300, "utility"),
    ("XEROX TONER + A4 REAMS", -1800, "office_expense"),
]


def test_hasher_cannot_read_real_bank_narration(semantic_only):
    """Documents a known limitation. Expected to FAIL once a true sentence
    embedder replaces HashingEmbedder -- that is the acceptance criterion."""
    correct = sum(
        semantic_only.categorize(d, a).category == exp for d, a, exp in REALISTIC_NARRATIONS
    )
    assert correct <= 1, (
        "HashingEmbedder unexpectedly classified real narrations. If you swapped "
        "in a real embedder, delete this test and raise MIN_SEMANTIC_ACCURACY."
    )


def test_low_confidence_never_produces_a_confident_wrong_answer(semantic_only):
    """The safety property that makes the above acceptable: when the embedder
    is out of its depth it must abstain, not guess."""
    for desc, amount, expected in REALISTIC_NARRATIONS:
        r = semantic_only.categorize(desc, amount)
        if r.category != expected:
            assert r.tier == "fallback", f"{desc!r} was wrong AND confident (tier={r.tier})"
            assert r.confidence == 0.0
