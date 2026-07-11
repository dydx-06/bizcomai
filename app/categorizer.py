"""Transaction categorization: rules -> embeddings -> LLM.

Design notes
------------
The original code was rules -> LLM. That means every unseen merchant string
costs a network round-trip and returns a non-deterministic answer, which makes
the pipeline slow and the test suite flaky.

Inserting an embedding tier fixes both. Each category is described by a handful
of prototype phrases; a transaction is assigned to the category whose prototypes
it is most similar to. Only when the top similarity falls below
`SEMANTIC_FLOOR`, or the margin over the runner-up is too thin to trust, do we
escalate to the LLM.

Every decision carries a `CategoryResult.tier` so you can audit -- in the report
-- what fraction of real transactions each tier actually resolved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from .embeddings import Embedder, HashingEmbedder, cosine_similarity

ALLOWED_CATEGORIES = [
    "supplier_payment",
    "gst_payment",
    "loan_emi",
    "utility",
    "customer_receipt",
    "salary",
    "rent",
    "office_expense",
    "uncategorized_expense",
    "uncategorized_income",
]

# Categories that are only reachable given the sign of the amount. A credit can
# never be a GST payment; a debit can never be a customer receipt. Enforcing
# this removes a whole class of embarrassing misclassification.
DEBIT_ONLY = {"supplier_payment", "gst_payment", "loan_emi", "utility", "salary", "rent", "office_expense"}
CREDIT_ONLY = {"customer_receipt"}

# Tier 1. Unambiguous string signals. Cheap, exact, and always right.
CATEGORY_RULES: Dict[str, List[str]] = {
    "supplier_payment": ["indiamart", "wholesale", "logistics", "metals"],
    "gst_payment": ["gst", "cbic", "gstn"],
    "loan_emi": ["emi", "bajaj", "muthoot", "hdfc loan"],
    "utility": ["bescom", "mahavitaran", "jio", "airtel", "tneb", "torrent power"],
    "customer_receipt": ["razorpay", "instamojo", "ccavenue"],
    "salary": ["salary", "payroll", "wages"],
    "rent": ["rent", "lease"],
}

# Tier 2. Prototype phrases per category. These are what get embedded.
# More prototypes = better coverage; keep them phrased like real narrations.
CATEGORY_PROTOTYPES: Dict[str, List[str]] = {
    "supplier_payment": [
        "payment to raw material vendor",
        "purchase of steel sheets from supplier",
        "freight and transport charges to distributor",
        "paid trading company for inventory stock",
    ],
    "gst_payment": [
        "goods and services tax challan payment",
        "quarterly tax remittance to government",
        "tds and statutory tax deposit",
    ],
    "loan_emi": [
        "monthly loan instalment debit",
        "equated monthly instalment to finance company",
        "term loan repayment to bank",
    ],
    "utility": [
        "monthly electricity bill payment",
        "broadband and mobile recharge",
        "water and power board bill",
    ],
    "customer_receipt": [
        "payment received from customer against invoice",
        "sales proceeds credited to account",
        "client settled outstanding bill",
    ],
    "salary": [
        "monthly staff salary disbursement",
        "wages paid to workers",
    ],
    "rent": [
        "monthly shop rent paid to landlord",
        "godown lease payment",
    ],
    "office_expense": [
        "stationery and printer cartridges",
        "office tea coffee and pantry supplies",
        "courier and postage charges",
    ],
}

SEMANTIC_FLOOR = 0.42  # below this, similarity is noise
MARGIN_FLOOR = 0.05  # top-1 must beat top-2 by this much


@dataclass(frozen=True)
class CategoryResult:
    category: str
    tier: str  # "rule" | "semantic" | "llm" | "fallback"
    confidence: float
    reason: str = ""


def _fallback(amount: float) -> str:
    return "uncategorized_expense" if amount < 0 else "uncategorized_income"


def _sign_allows(category: str, amount: float) -> bool:
    if amount < 0 and category in CREDIT_ONLY:
        return False
    if amount >= 0 and category in DEBIT_ONLY:
        return False
    return True


class SemanticCategorizer:
    """Injectable, offline-testable, three-tier categorizer.

    `llm_fn` is a callable (description, amount) -> category string, or None to
    disable the LLM tier entirely (which is what the test suite does).
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        llm_fn: Optional[Callable[[str, float], str]] = None,
        semantic_floor: float = SEMANTIC_FLOOR,
        margin_floor: float = MARGIN_FLOOR,
        prototypes: Optional[Dict[str, List[str]]] = None,
        rules: Optional[Dict[str, List[str]]] = None,
    ):
        self.embedder = embedder or HashingEmbedder()
        self.llm_fn = llm_fn
        self.semantic_floor = semantic_floor
        self.margin_floor = margin_floor
        self.prototypes = prototypes if prototypes is not None else CATEGORY_PROTOTYPES
        self.rules = rules if rules is not None else CATEGORY_RULES
        self._proto_matrix: Optional[np.ndarray] = None
        self._proto_labels: List[str] = []
        self._cache: Dict[str, CategoryResult] = {}

    # -- tier 1 -----------------------------------------------------------
    @staticmethod
    def _keyword_hit(keyword: str, text: str) -> bool:
        """Short keywords must match a whole word.

        Plain substring matching is a trap: 'emi' is inside 'r-EMI-ttance',
        'pr-EMI-um' and 'ch-EMI-cals', so a GST remittance was being tagged as a
        loan EMI. Keywords of 4+ characters are distinctive enough for substring
        matching; anything shorter needs a word boundary.
        """
        if len(keyword) >= 4 and " " not in keyword:
            return keyword in text
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None

    def _rule_match(self, desc_lower: str, amount: float) -> Optional[CategoryResult]:
        for category, keywords in self.rules.items():
            for kw in keywords:
                if self._keyword_hit(kw, desc_lower) and _sign_allows(category, amount):
                    return CategoryResult(category, "rule", 1.0, f"matched keyword {kw!r}")
        return None

    # -- tier 2 -----------------------------------------------------------
    def _build_prototypes(self) -> None:
        if self._proto_matrix is not None:
            return
        texts, labels = [], []
        for category, phrases in self.prototypes.items():
            for p in phrases:
                texts.append(p)
                labels.append(category)
        self._proto_labels = labels
        # An empty prototype set is valid configuration (it disables this tier),
        # so encode() must not be handed an empty list.
        self._proto_matrix = self.embedder.encode(texts) if texts else np.empty((0, 0))

    def _semantic_match(self, description: str, amount: float) -> Optional[CategoryResult]:
        self._build_prototypes()
        if self._proto_matrix is None or self._proto_matrix.shape[0] == 0:
            return None

        vec = self.embedder.encode([description])
        sims = cosine_similarity(vec, self._proto_matrix)[0]

        # Best similarity per category, respecting the debit/credit constraint.
        by_cat: Dict[str, float] = {}
        for label, s in zip(self._proto_labels, sims):
            if not _sign_allows(label, amount):
                continue
            by_cat[label] = max(by_cat.get(label, -1.0), float(s))

        if not by_cat:
            return None

        ranked = sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
        top_cat, top_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

        if top_score < self.semantic_floor:
            return None
        if (top_score - runner_up) < self.margin_floor:
            return None  # too close to call; escalate
        return CategoryResult(
            top_cat, "semantic", top_score, f"cosine {top_score:.3f}, margin {top_score - runner_up:.3f}"
        )

    # -- tier 3 -----------------------------------------------------------
    def _llm_match(self, description: str, amount: float) -> Optional[CategoryResult]:
        if self.llm_fn is None:
            return None
        try:
            category = self.llm_fn(description, amount)
        except Exception as exc:  # network, rate limit, malformed response
            return CategoryResult(_fallback(amount), "fallback", 0.0, f"llm error: {exc}")
        if category in ALLOWED_CATEGORIES and _sign_allows(category, amount):
            return CategoryResult(category, "llm", 0.5, "llm classification")
        return CategoryResult(_fallback(amount), "fallback", 0.0, "llm returned invalid category")

    # -- public -----------------------------------------------------------
    def categorize(self, description: str, amount: float) -> CategoryResult:
        desc = str(description or "").strip()
        if not desc:
            return CategoryResult(_fallback(amount), "fallback", 0.0, "empty description")

        key = f"{desc.lower()}|{'d' if amount < 0 else 'c'}"
        if key in self._cache:
            return self._cache[key]

        result = (
            self._rule_match(desc.lower(), amount)
            or self._semantic_match(desc, amount)
            or self._llm_match(desc, amount)
            or CategoryResult(_fallback(amount), "fallback", 0.0, "no tier matched")
        )
        self._cache[key] = result
        return result

    def categorize_many(self, rows: Sequence[tuple[str, float]]) -> List[CategoryResult]:
        return [self.categorize(d, a) for d, a in rows]


def build_groq_llm_fn(model: str = "llama-3.1-8b-instant") -> Callable[[str, float], str]:
    """Factory for the production LLM tier. Imported lazily so that neither the
    test suite nor a Groq-less deployment pays for the dependency."""

    def _fn(description: str, amount: float) -> str:
        import os

        from groq import Groq  # noqa: PLC0415

        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        prompt = (
            "You are an expert Indian SME accountant. Categorize this bank "
            f"transaction description: '{description}'. The amount is {amount} "
            "(negative = money leaving the business, positive = money entering).\n"
            f"Choose EXACTLY ONE category from: {ALLOWED_CATEGORIES}\n"
            "Return ONLY the category name. No quotes, punctuation, or explanation."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()

    return _fn
