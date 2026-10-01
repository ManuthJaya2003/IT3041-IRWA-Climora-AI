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

## Regression tests

- `backend/tests/test_api_guards.py` — 7 tests (auth, rate limits, history)
- `backend/tests/test_billing.py` — 5 tests (plans, quotas, usage)
- `backend/tests/test_history.py` — 4 tests (memory cache, SQL persistence, PG fallback)
- Frontend: `npm run build` (`tsc -b` + vite) must pass clean.
