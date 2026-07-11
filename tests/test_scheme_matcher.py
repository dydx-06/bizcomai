import pytest

from app.scheme_matcher import GATES, GOVT_SCHEMES, SchemeMatcher, match_schemes


def names(matches):
    return [m.scheme_name for m in matches]


# --- Hard eligibility gates: the core safety property ------------------------

def test_ineligible_scheme_never_appears_regardless_of_semantic_similarity(matcher):
    """A male-owned EXISTING trading firm asks explicitly for a Stand-Up India
    style loan. Semantic similarity is high. Eligibility is zero. It must not
    be recommended. This is the whole reason gates are not embeddings."""
    business = {
        "sector": "Trading",
        "is_new_business": False,
        "women_owned": False,
        "sc_st_owned": False,
        "turnover_inr": 5_000_000,
    }
    need = "term loan for a first time woman or SC ST entrepreneur starting a new enterprise"
    result = matcher.match(business, need_text=need)
    assert "Stand-Up India Scheme" not in names(result)


def test_standup_requires_both_greenfield_and_special_category(matcher):
    base = {"sector": "Services", "turnover_inr": 0}
    gate = GATES["standup_01"]
    assert gate({**base, "is_new_business": True, "women_owned": True})[0] == 80
    assert gate({**base, "is_new_business": True, "sc_st_owned": True})[0] == 80
    assert gate({**base, "is_new_business": False, "women_owned": True})[0] == 0
    assert gate({**base, "is_new_business": True, "women_owned": False})[0] == 0


def test_clcss_excluded_for_new_business(matcher):
    assert GATES["clcss_01"]({"is_new_business": True, "needs_tech_upgrade": True})[0] == 0


def test_clcss_requires_tech_upgrade_flag():
    assert GATES["clcss_01"]({"is_new_business": False, "needs_tech_upgrade": False})[0] == 0


def test_pmegp_excluded_for_existing_business():
    assert GATES["pmegp_01"]({"is_new_business": False})[0] == 0


def test_samadhaan_only_with_overdue_receivables():
    assert GATES["samadhaan_01"]({"has_overdue_receivables_45_days": True})[0] == 90
    assert GATES["samadhaan_01"]({"has_overdue_receivables_45_days": False})[0] == 0


@pytest.mark.parametrize(
    "loan,eligible", [(0, False), (50_000, True), (500_000, True), (1_000_000, True), (1_000_001, False)]
)
def test_mudra_loan_ceiling_is_exactly_ten_lakh(loan, eligible):
    assert (GATES["pmmy_01"]({"required_loan_inr": loan})[0] > 0) is eligible


@pytest.mark.parametrize(
    "loan,band", [(40_000, "Shishu"), (300_000, "Kishor"), (900_000, "Tarun")]
)
def test_mudra_reports_correct_band(loan, band):
    _, reasons = GATES["pmmy_01"]({"required_loan_inr": loan})
    assert band in reasons[0]


# --- Sector filter ----------------------------------------------------------

def test_manufacturing_only_schemes_hidden_from_services(matcher):
    business = {"sector": "Services", "is_new_business": False, "needs_tech_upgrade": True, "turnover_inr": 1_000_000}
    result = names(matcher.match(business))
    assert "Credit Linked Capital Subsidy Scheme (CLCSS)" not in result
    assert "MSME Sustainable (ZED) Certification" not in result


def test_unknown_sector_returns_no_matches(matcher):
    assert matcher.match({"sector": "Cryptocurrency Mining", "is_new_business": False}) == []


def test_missing_sector_returns_no_matches(matcher):
    assert matcher.match({"is_new_business": False}) == []


# --- Profile-level behaviour ------------------------------------------------

def test_established_manufacturer_gets_expected_schemes(matcher, established_manufacturer):
    result = names(matcher.match(established_manufacturer))
    assert "MSME Samadhaan (Delayed Payment Resolution)" in result
    assert "Credit Linked Capital Subsidy Scheme (CLCSS)" in result
    assert "Prime Minister's Employment Generation Programme (PMEGP)" not in result


def test_new_woman_entrepreneur_gets_standup_and_pmegp(matcher, new_woman_entrepreneur):
    result = names(matcher.match(new_woman_entrepreneur))
    assert "Stand-Up India Scheme" in result
    assert "Prime Minister's Employment Generation Programme (PMEGP)" in result


def test_samadhaan_ranks_first_for_overdue_business(matcher, established_manufacturer):
    """Overdue receivables score 90 -- the most urgent thing this user has."""
    result = matcher.match(established_manufacturer)
    assert result[0].scheme_name == "MSME Samadhaan (Delayed Payment Resolution)"


def test_results_are_sorted_by_score_descending(matcher, established_manufacturer):
    scores = [m.match_score for m in matcher.match(established_manufacturer)]
    assert scores == sorted(scores, reverse=True)


def test_udyam_registration_boosts_score(matcher):
    base = {"sector": "Manufacturing", "is_new_business": False, "needs_tech_upgrade": True, "turnover_inr": 1_000_000}
    without = matcher.match({**base, "udyam_registered": False})
    with_udyam = matcher.match({**base, "udyam_registered": True})
    assert with_udyam[0].rule_score > without[0].rule_score


def test_scores_never_exceed_one_hundred(matcher, established_manufacturer):
    assert all(m.match_score <= 100 for m in matcher.match(established_manufacturer))


def test_every_match_carries_reasons_and_a_url(matcher, established_manufacturer):
    for m in matcher.match(established_manufacturer):
        assert m.eligibility_reasons.strip()
        assert m.application_url.startswith("https://")


# --- Semantic ranking layer -------------------------------------------------

def test_semantic_need_reorders_among_eligible_schemes(embedder):
    """Both CLCSS and ZED are eligible. Stating a machinery need should lift
    CLCSS's semantic score above ZED's, without either becoming ineligible."""
    m = SchemeMatcher(embedder=embedder, semantic_weight=0.9, threshold=0.0)
    business = {
        "sector": "Manufacturing",
        "is_new_business": False,
        "needs_tech_upgrade": True,
        "turnover_inr": 1_000_000,
    }
    result = m.match(business, need_text="subsidy to buy new machinery and upgrade plant technology and equipment")
    by_name = {x.scheme_name: x for x in result}
    clcss = by_name["Credit Linked Capital Subsidy Scheme (CLCSS)"]
    zed = by_name["MSME Sustainable (ZED) Certification"]
    assert clcss.semantic_score > zed.semantic_score


def test_semantic_score_is_zero_when_no_need_text_given(matcher, established_manufacturer):
    for m in matcher.match(established_manufacturer, need_text=""):
        assert m.semantic_score == 0.0


def test_need_text_does_not_change_rule_score(matcher, established_manufacturer):
    a = {m.scheme_name: m.rule_score for m in matcher.match(established_manufacturer)}
    b = {m.scheme_name: m.rule_score for m in matcher.match(established_manufacturer, "I want a loan")}
    assert a == b


# --- Sector inference -------------------------------------------------------

def test_infer_sector_returns_a_canonical_sector(matcher):
    sector, score = matcher.infer_sector("we run a small workshop machining auto parts")
    assert sector in {"Manufacturing", "Services", "Trading", "Agro-Industry"}
    assert 0.0 <= score <= 1.0


def test_business_description_is_used_when_sector_missing(matcher):
    business = {
        "business_description": "wholesale and retail buying and reselling of goods",
        "is_new_business": False,
        "turnover_inr": 1_000_000,
    }
    assert matcher.match(business), "sector inference should have unlocked Trading schemes"


# --- Wrapper and data integrity ---------------------------------------------

def test_functional_wrapper_returns_json_safe_dicts(established_manufacturer):
    out = match_schemes(established_manufacturer)
    assert isinstance(out, list) and isinstance(out[0], dict)
    assert "match_score" in out[0]


def test_every_scheme_has_a_gate():
    assert {s.scheme_id for s in GOVT_SCHEMES} == set(GATES.keys())


def test_every_scheme_has_a_semantic_profile():
    assert all(s.semantic_profile.strip() for s in GOVT_SCHEMES)
