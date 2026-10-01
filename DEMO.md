# Climora AI — Final Viva Demo Script (~8 minutes)

## 0. Setup (before examiners arrive)

```bash
# Terminal 1 — backend (from repo root)
cd backend && uvicorn app.main:app --port 8000
# Terminal 2 — frontend
cd frontend && npm run dev
```

Open `http://localhost:5173`. Confirm backend docs at `http://localhost:8000/docs`.

## 1. The problem → the product (1 min)

"Climate information is scattered across weather services, government
sources and news — hard to interpret and act on. Climora coordinates 7
specialized agents to retrieve evidence, assess risk, verify claims, and
recommend actions — in English, Sinhala and Tamil."

## 2. Live trilingual queries (3 min)

Click each suggestion card in turn; point at the risk badge, evidence
sources, and confidence on every answer:

1. `What is the current weather in Colombo?` — weather + live data
2. `Is there a flood risk in Kandy right now?` — **HIGH** risk + recommendations
3. Sinhala monsoon query — answer arrives **in Sinhala**
4. Tamil Nuwara Eliya landslide query — answer arrives **in Tamil**

Say: "Language is auto-detected by script — no manual toggle needed."

## 3. Commercialization working (2 min)

- Sidebar → plan card shows live quota % → open pricing → switch Free → Premium:
  quota jumps 100 → 1,000 instantly (Settings → Subscription proves it).
- Settings → Notifications on Free shows the Premium lock (upsell enforced).
- Exhaust-quota demo (optional): lower the Free quota and hammer queries
  to show the 429 + upgrade hint — or just describe it.

## 4. Engineering depth (2 min, if asked)

- `EVALUATION.md`: 100% location/topic accuracy, 68.8% TF-IDF retrieval —
  and the eval caught 2 real bugs we fixed (Tamil Colombo inflection,
  heat-wave topic ordering).
- `backend/tests/`: 12 regression tests (auth, quotas, rate limits).
- Responsible AI: every answer grounded in retrieved evidence, verification
  agent, confidence scores, disclaimers, no internal errors leaked.

## Likely questions (one-line answers)

- *"Why not just ChatGPT?"* — uncontrolled single model vs. orchestrated
  retrieval → analysis → verification → recommendation with cited evidence.
- *"What is genuinely agentic?"* — 6 MCP agent servers + orchestrator with
  structured task messages, retries, and fallbacks (kill an agent port and
  the pipeline still answers).
- *"Biggest limitation?"* — lexical retrieval for Sinhala/Tamil (68.8%);
  mitigation is live data + LLM synthesis; multilingual embeddings are next.
- *"Payments/teams/dashboards?"* — scoped out; quotas, saved locations,
  retention caps and alerts are the enforced subset. Stated, not hidden.
