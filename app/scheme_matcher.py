"""Government scheme matching.

Why this is NOT fully semantic
------------------------------
Stand-Up India requires a greenfield enterprise owned by a woman or an SC/ST
entrepreneur. That is a statutory condition, not a resemblance. A pure embedding
model will happily score an existing male-owned trading firm at 0.8 against the
scheme text, and the user will apply, and be rejected.

So eligibility stays a hard predicate. Semantics do two jobs the rules cannot:

  * `infer_sector` maps a free-text business description ("we do CNC job work
    for auto parts") onto a canonical sector, so the user need not pick from a
    dropdown.
  * `semantic_relevance` re-ranks schemes the business is *already eligible for*,
    against a stated need ("I want to buy a new lathe"), so the ranking reflects
    intent rather than a hand-tuned constant.

Final score = rule_score * (1 - SEMANTIC_WEIGHT) + semantic * 100 * SEMANTIC_WEIGHT
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional

from .embeddings import Embedder, HashingEmbedder, cosine_similarity

SEMANTIC_WEIGHT = 0.30
SCORE_THRESHOLD = 50.0

CANONICAL_SECTORS = {
    "Manufacturing": [
        "factory producing goods and components",
        "machining fabrication and assembly workshop",
        "textile garment and food processing unit",
    ],
    "Services": [
        "consultancy repair and professional services firm",
        "salon hospitality and logistics service provider",
        "software and IT enabled services company",
    ],
    "Trading": [
        "wholesale and retail buying and reselling of goods",
        "distributor stockist and shop retail business",
    ],
    "Agro-Industry": [
        "agricultural produce processing and rural agri business",
        "dairy poultry and farm based enterprise",
    ],
}


@dataclass(frozen=True)
class Scheme:
    scheme_id: str
    scheme_name: str
    description: str
    target_sectors: tuple
    application_url: str
    semantic_profile: str  # what need this scheme serves; embedded for ranking
    max_turnover_inr: Optional[int] = None


GOVT_SCHEMES: List[Scheme] = [
    Scheme(
        "cgtmse_01",
        "Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)",
        "Collateral-free loans up to \u20b95 Crore for MSMEs.",
        ("Manufacturing", "Services", "Trading"),
        "https://www.cgtmse.in/",
        "working capital loan without collateral security for business expansion",
        max_turnover_inr=500_000_000,
    ),
    Scheme(
        "pmegp_01",
        "Prime Minister's Employment Generation Programme (PMEGP)",
        "Up to 35% subsidy on new project costs (\u20b950L Mfg / \u20b920L Services).",
        ("Manufacturing", "Services"),
        "https://www.kviconline.gov.in/pmegpeportal/",
        "capital subsidy to start a brand new business venture and create employment",
    ),
    Scheme(
        "standup_01",
        "Stand-Up India Scheme",
        "Bank loans between \u20b910 Lakh and \u20b91 Crore for greenfield enterprises by Women/SC/ST.",
        ("Manufacturing", "Services", "Trading"),
        "https://www.standupmitra.in/",
        "term loan for a first time woman or SC ST entrepreneur starting a new enterprise",
    ),
    Scheme(
        "pmmy_01",
        "Pradhan Mantri Mudra Yojana (PMMY)",
        "Micro-credit up to \u20b910 Lakhs (Shishu, Kishor, Tarun) for non-corporate businesses.",
        ("Manufacturing", "Services", "Trading"),
        "https://www.mudra.org.in/",
        "small micro credit loan under ten lakh rupees for a tiny business",
    ),
    Scheme(
        "clcss_01",
        "Credit Linked Capital Subsidy Scheme (CLCSS)",
        "15% upfront capital subsidy for technology upgradation and new machinery.",
        ("Manufacturing",),
        "https://msme.gov.in/",
        "subsidy to buy new machinery and upgrade plant technology and equipment",
    ),
    Scheme(
        "zed_01",
        "MSME Sustainable (ZED) Certification",
        "Subsidies and support for adopting Zero Defect Zero Effect practices.",
        ("Manufacturing",),
        "https://zed.msme.gov.in/",
        "quality certification and improving manufacturing standards and reducing defects",
    ),
    Scheme(
        "samadhaan_01",
        "MSME Samadhaan (Delayed Payment Resolution)",
        "Legal recourse portal to recover delayed payments (overdue > 45 days).",
        ("Manufacturing", "Services", "Trading"),
        "https://samadhaan.msme.gov.in/",
        "recovering overdue unpaid invoices and delayed payments from buyers legally",
    ),
    Scheme(
        "aspire_01",
        "ASPIRE (Innovation & Rural Industry)",
        "Support for livelihood business incubators in agro-based and rural industries.",
        ("Manufacturing", "Agro-Industry"),
        "https://aspire.msme.gov.in/",
        "rural innovation incubation support for agro based village industry",
    ),
]

SCHEMES_BY_ID = {s.scheme_id: s for s in GOVT_SCHEMES}


@dataclass
class SchemeMatch:
    scheme_name: str
    description: str
    match_score: float
    rule_score: float
    semantic_score: float
    eligibility_reasons: str
    application_url: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Hard eligibility gates -------------------------------------------------
# Each returns (rule_score, reasons). A score of 0 means "not eligible".
# These encode statute. Do not replace them with cosine similarity.

Gate = Callable[[Dict], tuple]


def _cgtmse(b: Dict) -> tuple:
    score, reasons = 0.0, []
    cap = SCHEMES_BY_ID["cgtmse_01"].max_turnover_inr or 0
    if b.get("turnover_inr", 0) <= cap:
        score += 40
        reasons.append("Meets turnover criteria (< \u20b950 Cr).")
    if not b.get("is_new_business"):
        score += 20
        reasons.append("Applicable for existing business expansion.")
    return score, reasons


def _pmegp(b: Dict) -> tuple:
    if not b.get("is_new_business"):
        return 0.0, []
    score, reasons = 50.0, ["Eligible as a new business venture."]
    if b.get("women_owned") or b.get("sc_st_owned") or b.get("rural_location"):
        score += 30
        reasons.append("Qualifies for higher subsidy bracket (Special Category/Rural).")
    return score, reasons


def _standup(b: Dict) -> tuple:
    if b.get("is_new_business") and (b.get("women_owned") or b.get("sc_st_owned")):
        return 80.0, ["Meets strict criteria: new greenfield project by a woman or SC/ST entrepreneur."]
    return 0.0, []


def _pmmy(b: Dict) -> tuple:
    loan = b.get("required_loan_inr", 0)
    if not (0 < loan <= 1_000_000):
        return 0.0, []
    if loan <= 50_000:
        band = "Shishu category loan (up to \u20b950k)."
    elif loan <= 500_000:
        band = "Kishor category loan (up to \u20b95L)."
    else:
        band = "Tarun category loan (up to \u20b910L)."
    return 70.0, [f"Eligible for {band}"]


def _clcss(b: Dict) -> tuple:
    if not b.get("is_new_business") and b.get("needs_tech_upgrade"):
        return 75.0, ["Eligible for 15% machinery/tech upgradation subsidy."]
    return 0.0, []


def _zed(b: Dict) -> tuple:
    if not b.get("is_new_business"):
        return 60.0, ["Eligible for subsidies on quality standard certification."]
    return 0.0, []


def _samadhaan(b: Dict) -> tuple:
    if b.get("has_overdue_receivables_45_days"):
        return 90.0, ["CRITICAL: receivables overdue by 45+ days. Legal recourse available."]
    return 0.0, []


def _aspire(b: Dict) -> tuple:
    if b.get("rural_location") or b.get("sector") == "Agro-Industry":
        return 65.0, ["Eligible for rural innovation and incubation support."]
    return 0.0, []


GATES: Dict[str, Gate] = {
    "cgtmse_01": _cgtmse,
    "pmegp_01": _pmegp,
    "standup_01": _standup,
    "pmmy_01": _pmmy,
    "clcss_01": _clcss,
    "zed_01": _zed,
    "samadhaan_01": _samadhaan,
    "aspire_01": _aspire,
}


class SchemeMatcher:
    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        semantic_weight: float = SEMANTIC_WEIGHT,
        threshold: float = SCORE_THRESHOLD,
        schemes: Optional[List[Scheme]] = None,
    ):
        self.embedder = embedder or HashingEmbedder()
        self.semantic_weight = semantic_weight
        self.threshold = threshold
        self.schemes = schemes if schemes is not None else GOVT_SCHEMES
        self._sector_matrix = None
        self._sector_labels: List[str] = []

    def infer_sector(self, free_text: str) -> tuple:
        """Map a free-text business description onto a canonical sector.

        Returns (sector, confidence). Lets the user type "we run a CNC job shop"
        instead of picking from a dropdown they may not understand.
        """
        if self._sector_matrix is None:
            texts, labels = [], []
            for sector, protos in CANONICAL_SECTORS.items():
                for p in protos:
                    texts.append(p)
                    labels.append(sector)
            self._sector_matrix = self.embedder.encode(texts)
            self._sector_labels = labels

        sims = cosine_similarity(self.embedder.encode([free_text]), self._sector_matrix)[0]
        best: Dict[str, float] = {}
        for label, s in zip(self._sector_labels, sims):
            best[label] = max(best.get(label, -1.0), float(s))
        sector, score = max(best.items(), key=lambda kv: kv[1])
        return sector, score

    def _semantic_relevance(self, need_text: str, schemes: List[Scheme]) -> Dict[str, float]:
        """Cosine of the stated need against each scheme's semantic profile."""
        if not need_text.strip():
            return {s.scheme_id: 0.0 for s in schemes}
        need_vec = self.embedder.encode([need_text])
        proto = self.embedder.encode([s.semantic_profile for s in schemes])
        sims = cosine_similarity(need_vec, proto)[0]
        return {s.scheme_id: max(0.0, float(sim)) for s, sim in zip(schemes, sims)}

    def match(self, business: Dict, need_text: str = "") -> List[SchemeMatch]:
        sector = business.get("sector")
        if not sector and business.get("business_description"):
            sector, _ = self.infer_sector(business["business_description"])

        eligible = [s for s in self.schemes if sector in s.target_sectors]
        relevance = self._semantic_relevance(need_text, eligible)

        matches: List[SchemeMatch] = []
        for scheme in eligible:
            gate = GATES.get(scheme.scheme_id)
            if gate is None:
                continue
            rule_score, reasons = gate(business)
            if rule_score <= 0:
                continue  # hard-ineligible: semantics cannot rescue it

            if business.get("udyam_registered"):
                rule_score += 15
                reasons.append("Udyam registration verified.")
            rule_score = min(rule_score, 100.0)

            sem = relevance.get(scheme.scheme_id, 0.0)
            w = self.semantic_weight if need_text.strip() else 0.0
            final = rule_score * (1 - w) + (sem * 100.0) * w

            if final >= self.threshold:
                matches.append(
                    SchemeMatch(
                        scheme_name=scheme.scheme_name,
                        description=scheme.description,
                        match_score=round(min(final, 100.0), 2),
                        rule_score=round(rule_score, 2),
                        semantic_score=round(sem, 4),
                        eligibility_reasons=" | ".join(reasons),
                        application_url=scheme.application_url,
                    )
                )

        return sorted(matches, key=lambda m: m.match_score, reverse=True)


def match_schemes(business: Dict, need_text: str = "", matcher: Optional[SchemeMatcher] = None) -> List[Dict]:
    """Backwards-compatible functional wrapper."""
    return [m.to_dict() for m in (matcher or SchemeMatcher()).match(business, need_text)]
