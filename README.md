# Cashflow Intelligence & Scheme Matcher (Person C)

Semantic transaction categorization, cashflow forecasting, and government scheme
matching for the MSME AI Advisor.

## Run

```bash
pip install -r requirements.txt
pytest                       # 179 tests, ~1s, fully offline
pytest --cov=app             # 93% coverage
pytest tests/test_accuracy.py -s   # prints the accuracy tables for the report
uvicorn app.main:app --reload
```

## Architecture

```
CSV ──► parser ──► categorizer (3 tiers) ──► pipeline ──► FastAPI
                                              ├── forecasting
                                              └── scheme_matcher (gates + semantics)
```

`app/pipeline.py` is the single source of truth. `app/main.py` only handles HTTP.
The old `intelligence_layer.py` duplicated the endpoint's logic; both copies are
now one.

### Categorization: three tiers, not two

| Tier | Mechanism | Cost | Determinism |
|---|---|---|---|
| 1 | Keyword rules | free | exact |
| 2 | Embedding similarity vs. prototype phrases | cheap, cached | deterministic |
| 3 | LLM (Groq) | slow, paid | non-deterministic |

The original design was rules → LLM, so every unseen merchant string cost a
network round trip. Tier 2 absorbs most of that. A tier only answers if its top
cosine score clears `SEMANTIC_FLOOR` **and** beats the runner-up by
`MARGIN_FLOOR`; otherwise it abstains and escalates. Every result carries
`.tier`, so `categorization_tiers` in the API response tells you what fraction
each tier actually resolved — a number worth putting in the report.

Debit/credit constraints are enforced structurally: a credit can never be a GST
payment, a debit can never be a customer receipt. This holds even when the LLM
says otherwise.

### Scheme matching: why it is *not* fully semantic

Stand-Up India requires a greenfield enterprise owned by a woman or SC/ST
entrepreneur. That is statute, not resemblance. An embedding model will happily
score an existing male-owned trading firm at 0.8 against the scheme text, and
that user will apply and be rejected.

So **eligibility stays a hard predicate** (`GATES` in `scheme_matcher.py`).
Semantics do the two jobs rules cannot:

- `infer_sector()` — maps free text ("we do CNC job work for auto parts") onto a
  canonical sector, so users needn't pick from a dropdown they don't understand.
- `_semantic_relevance()` — re-ranks schemes the business is *already eligible
  for* against a stated need, so ordering reflects intent.

`final = rule_score × (1 − w) + semantic × 100 × w`, with `w = 0` when no need
text is supplied. Semantics reorder; they never unlock.

`test_ineligible_scheme_never_appears_regardless_of_semantic_similarity` pins
this down. Replace the gates with cosine similarity and it goes red.

## Bugs found and fixed

Each has a named regression test.

1. **Burn rate divided by wrong denominator.** Original: `total_outflow /
   len(distinct_expense_days)`. A business spending on 12 days of a 90-day
   statement had its burn overstated 7.5×, flipping a healthy company to
   `CRITICAL`. Fixed to divide by calendar span.
   → `test_burn_rate_divides_by_calendar_span_not_distinct_expense_days`

2. **`des-CR-iption` column collision.** `CREDIT_HINTS` contained `"cr"`, matched
   as a substring, so the description column was selected as the credit column
   and the parser tried to read `"RAZORPAY SETTLEMENT"` as a number. Two-letter
   hints now require whole-token matches.
   → `test_signed_amount_csv_parses_and_signs_correctly`

3. **`r-EMI-ttance` keyword collision.** `"emi"` is a substring of *remittance*,
   *premium*, and *chemicals*, so a GST remittance was tagged `loan_emi`.
   Keywords under 4 chars now need a word boundary.
   → `test_short_keyword_emi_does_not_match_inside_longer_words`

4. **Split withdrawal/deposit columns silently mis-signed.** Original mapped both
   onto `"amount"`; whichever came last won, so half the transactions had the
   wrong sign. This is the format most Indian banks actually export.
   → `test_split_columns_assign_correct_signs`

5. **Temp file leaked on every failed upload.** `os.remove()` sat on the success
   path only. Moved to `finally`.
   → `test_temp_file_removed_even_when_parsing_fails`

6. **Startup hook clobbered injected test doubles.** Module globals plus
   `@app.on_event("startup")` meant `TestClient` overwrote the fakes. Harmless
   today; the day `GROQ_API_KEY` appears in CI, the API tests would start making
   live calls. Now `lifespan` + `app.state` + `Depends`.
   → `test_startup_does_not_clobber_injected_dependencies`

7. **`np.vstack([])` on an empty prototype set.** An empty prototype dict is
   valid configuration (it disables tier 2) but crashed the embedder.

## Measured results

`pytest tests/test_accuracy.py -s` prints these.

| Benchmark | Result | What it means |
|---|---|---|
| Easy golden set (20 rows) | 100% | **Resolved 100% by tier 1.** Says nothing about semantics. |
| Hard golden set, tier 2 only (10 rows) | 100% | Rules and LLM disabled. Semantics work — but rows are paraphrases of the prototypes. |
| Realistic bank narration, tier 2 only (5 rows) | **0%** | `HashingEmbedder` cannot read `UPI/9823/SHREE ENTERPRISES/PURCH`. |

That last row is the honest one, and it is why `HashingEmbedder` is a **test
double and offline fallback, not a production embedder**. It fails *safely*:
every miss returns `tier="fallback"` at `0.00` confidence rather than a confident
wrong answer, so those rows escalate to the LLM in production. That property is
itself tested by
`test_low_confidence_never_produces_a_confident_wrong_answer`.

Do not report "100% accuracy" on the strength of the first row alone. Report the
tier breakdown alongside it.

## Upgrading to real embeddings

```bash
pip install sentence-transformers
```

`app/main.py` then picks up `SentenceTransformerEmbedder` automatically and falls
back to hashing if the model can't load. The default model is
`paraphrase-multilingual-MiniLM-L12-v2` — chosen because Indian bank narrations
are frequently transliterated Hindi/Marathi, which monolingual MiniLM handles
poorly.

When you do this, `test_hasher_cannot_read_real_bank_narration` is **expected to
fail**. That failure is the acceptance criterion for the upgrade. Delete it, and
raise `MIN_SEMANTIC_ACCURACY`.

## Testing notes

- `tests/conftest.py` installs an autouse guard that raises on any outbound
  socket connection. The suite is offline by construction, not by convention.
  (`test_network_guard_is_active` proves the guard fires.)
- The `llm_fn` seam means no test needs `GROQ_API_KEY`.
- `StubEmbedder` raises `KeyError` on unknown input, so a test can never
  silently pass on a vector the author forgot to define.
- Two tests guard other tests: `test_hard_golden_rows_are_not_solvable_by_keyword_rules`
  fails if someone adds a keyword that makes the semantic benchmark meaningless.
