# Climora AI — Evaluation Results

Measured with `backend/scripts/evaluate_ir.py` (deterministic, offline:
rule-based NLP + local FAISS store, no LLM calls, re-runnable by examiners).

## Method

Golden set of **16 queries** — 8 English, 4 Sinhala, 4 Tamil — each with an
expected district and climate topic. Three metrics:

| Metric | What it measures | How |
|---|---|---|
| Location accuracy | NLP gazetteer extracts the right district | Exact match on expected district |
| Topic accuracy | NLP assigns the right hazard/topic | Exact match on expected topic |
| Retrieval hit rate | FAISS top-3 contains relevant evidence | Expected location/topic terms in top-3 docs |

## Results (2026-10-01, 187 seeded documents)

- **Location accuracy: 16/16 = 100%**
- **Topic accuracy: 16/16 = 100%**
- **Retrieval top-3 hit rate: 13/16 = 81.2%** (was 68.8% before the
  cross-lingual bridge — see below)

Remaining misses (all thin-corpus districts): Nuwara Eliya landslide (EN),
Trincomalee cyclone (EN), Colombo weather (TA).

## What the evaluation caught (fixed before final)

1. **Tamil Colombo inflection** — `கொழும்பில்` (locative) changes the stem
   vowel, so substring matching on `கொழும்பு` failed. Fixed with a
   vowel-stripped stem entry (`கொழும்ப`).
2. **Topic ordering bug** — "Heat wave conditions in Colombo" classified as
   generic `temperature` because the `conditions` trigger was checked first.
   Fixed by ordering the `heat-wave` hazard before generic weather terms
   (verified plain "hot" queries still classify correctly).

## Honest limitations (viva-ready answers)

- **TF-IDF retrieval is the bottleneck (81.2%)**, especially where the
  corpus is thin. Mitigations shipped: a cross-lingual query bridge
  (Sinhala/Tamil → English retrieval terms, offline, zero dependencies)
  plus live weather APIs, location-filtered evidence, and LLM synthesis.
- Next step for retrieval quality: multilingual embeddings so non-English
  queries match English documents semantically instead of lexically.
- Sample size is 16 hand-picked queries; a larger annotated set with
  precision@k and inter-annotator agreement is future work.

## End-to-end answer quality (`backend/scripts/evaluate_e2e.py`)

Scores final pipeline answers — not just retrieval — on 9 golden queries
(3 English, 3 Sinhala, 3 Tamil) across 10 checks: completed, correct answer
language, location mentioned, aspect coverage (≥1 of 2 evidence terms in the
answer), ≥1 source cited, risk assessment present, ≥2 recommendations,
disclaimer present, verification record present, confidence in [0, 1].

Runs offline: without Bedrock credentials the pipeline answers from
retrieved evidence via labeled extractive/static fallbacks (never silently),
so examiners can re-run with `python scripts/evaluate_e2e.py`. The harness
is hermetic — it pins the MCP client to unused ports so scores don't depend
on whether agent servers happen to be running. With Bedrock configured the
same script scores full LLM synthesis (higher aspect coverage expected).
Per-query rows + aggregates print to stdout; full detail is saved
to `backend/e2e_eval_results.json`.

<!-- E2E-RESULTS: replaced by the latest measured run below. -->

Latest measured run (2026-10-05, hermetic offline-fallback mode, 187 seeded
documents, Bedrock unreachable so answers come from retrieved evidence via
labeled extractive/static fallbacks):

| Check | Result |
|---|---|
| completed (non-empty answer) | 9/9 = 100% |
| correct answer language (EN/SI/TA routing) | 9/9 = 100% |
| location mentioned in answer | 9/9 = 100% |
| aspect coverage (≥1 of 2 evidence terms) | 9/9 = 100% |
| ≥1 source cited | 9/9 = 100% |
| risk assessment present | 9/9 = 100% |
| ≥2 recommendations | 9/9 = 100% |
| disclaimer present | 9/9 = 100% |
| verification record present | 9/9 = 100% |
| confidence in [0, 1] | 9/9 = 100% |

Avg latency 8.3s/query offline (dominated by MCP port-probe timeouts with
agent servers down, not model inference). Raw per-query rows:
`backend/e2e_eval_results.json`.

Honest limits: offline answers quote evidence rather than synthesizing it,
so aspect depth and fluency are below what Bedrock synthesis produces (the
same script measures that mode when credentials are configured). Fixing the
offline path also fixed three real bugs found during this work: LLM failure
crashed the whole pipeline, empty evidence was misreported as an off-topic
question, and the fallback NLP/IR chain was English-only despite the
trilingual promise.

## Regression tests

- `backend/tests/test_api_guards.py` — 7 tests (auth, rate limits, history)
- `backend/tests/test_billing.py` — 7 tests (plans, quotas, usage, refunds)
- `backend/tests/test_auth.py` — 2 tests (register/login, server-side plans)
- `backend/tests/test_history.py` — 4 tests (memory cache, SQL persistence, PG fallback)
- Frontend: `npm run build` (`tsc -b` + vite) must pass clean.
