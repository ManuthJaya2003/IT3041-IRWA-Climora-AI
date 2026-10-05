"""End-to-end answer-quality evaluation: full pipeline, not just retrieval.

Runs golden queries through OrchestratorAgent.process_user_query (agent
servers optional — fallbacks cover them) and scores each final answer on:

  completed, language_ok, location_mentioned, aspect_coverage,
  sources_cited, risk_present, recs_ok, disclaimer_present,
  verification_present, confidence_sane (+ latency_ms, informational)

Needs no AWS credentials: without Bedrock the pipeline answers from
retrieved evidence via clearly-labeled extractive/static fallbacks, so this
is re-runnable by examiners. With Bedrock configured the same script scores
full LLM synthesis instead (higher aspect coverage expected).

Usage:  python scripts/evaluate_e2e.py [--json out.json]
"""

import argparse
import asyncio
import json
import os
import sys
import time

# Hermetic evaluation: point the MCP client at dead ports so results never
# depend on whether agent servers happen to be running on this machine.
# Every agent call then takes the same deterministic fallback path.
# Must be set before any app.* import (settings loads at import time).
os.environ["MCP_SERVER_BASE_PORT"] = "8199"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# (query, expected_lang, location_aliases, expected_topic, aspect_keywords)
GOLDEN = [
    # English
    ("Is there a flood risk in Kandy right now?", "en",
     ["kandy"], "flood", ["flood", "mahaweli"]),
    ("What is the current weather in Colombo?", "en",
     ["colombo"], "temperature", ["colombo", "rainfall"]),
    ("What is the drought situation in Jaffna?", "en",
     ["jaffna"], "drought", ["drought", "jaffna"]),
    # Typo tolerance (normalization layer)
    ("Is there a flod risk in Kndy right now?", "en",
     ["kandy"], "flood", ["flood", "kandy"]),
    ("What is the weathe in Colomob?", "en",
     ["colombo"], "temperature", ["colombo", "weather"]),
    # Sinhala
    ("මහනුවර ගංවතුර අවදානමක් තිබේද?", "si",
     ["මහනුවර", "kandy"], "flood", ["flood", "මහනුවර"]),
    ("කොළඹ මෝසම් වර්ෂාවට සූදානම් වන්නේ කෙසේද?", "si",
     ["කොළඹ", "colombo"], "rain", ["colombo", "monsoon"]),
    ("යාපනයේ නියඟ තත්ත්වය කුමක්ද?", "si",
     ["යාපනය", "jaffna"], "drought", ["drought", "යාපනය"]),
    # Tamil
    ("கண்டியில் வெள்ள அபாயம் உள்ளதா?", "ta",
     ["கண்டி", "kandy"], "flood", ["flood", "கண்டி"]),
    ("கொழும்பில் வானிலை எப்படி?", "ta",
     ["கொழும்பு", "கொழும்ப", "colombo"], "temperature", ["colombo", "கொழும்ப"]),
    ("திருகோணமலையில் சூறாவளி ஆபத்து என்ன?", "ta",
     ["திருகோணமலை", "trincomalee"], "cyclone", ["cyclone", "திருகோணமலை"]),
]

CHECKS = [
    "completed", "language_ok", "location_mentioned", "aspect_coverage",
    "sources_cited", "risk_present", "recs_ok", "disclaimer_present",
    "verification_present", "confidence_sane",
]


def _full_text(resp) -> str:
    parts = [resp.summary or "", resp.detailed_analysis or ""]
    parts.extend(resp.extracted_facts or [])
    for r in resp.recommendations or []:
        parts.append(getattr(r, "action", "") or "")
    return "\n".join(parts).lower()


def score_one(query, lang, aliases, topic, aspects, resp, latency_ms) -> dict:
    text = _full_text(resp)
    loc_hit = any(a.lower() in text for a in aliases)
    aspect_hits = sum(1 for a in aspects if a.lower() in text)
    conf = resp.confidence_score
    return {
        "query": query,
        "expected_lang": lang,
        "latency_ms": round(latency_ms, 1),
        "completed": bool(resp.summary and len(resp.summary.strip()) > 20),
        "language_ok": (resp.language or "en") == lang,
        "location_mentioned": loc_hit,
        "aspect_coverage": f"{aspect_hits}/{len(aspects)}",
        "aspect_pass": aspect_hits >= 1,
        "sources_cited": len(resp.sources or []) >= 1,
        "n_sources": len(resp.sources or []),
        "risk_present": resp.risk_assessment is not None,
        "risk_level": getattr(resp.risk_assessment, "risk_level", None) and str(resp.risk_assessment.risk_level),
        "recs_ok": len(resp.recommendations or []) >= 2,
        "n_recs": len(resp.recommendations or []),
        "disclaimer_present": bool(resp.disclaimer),
        "verification_present": bool(resp.verification_results),
        "confidence_sane": conf is not None and 0.0 <= float(conf) <= 1.0,
        "confidence": conf,
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="e2e_eval_results.json")
    args = ap.parse_args()

    from app.services.vector_store_service import vector_store_service
    from app.services.llm_service import llm_service
    await vector_store_service.initialize()
    # NOTE: deliberately NOT calling llm_service.initialize(). Building a
    # boto3 client never validates credentials, so "available" would be True
    # with expired keys and every call would hang in network retries. Left
    # uninitialized, the pipeline uses fast evidence-based fallbacks.
    llm_mode = "bedrock" if llm_service.is_available() else "offline-fallback"
    print(f"LLM mode: {llm_mode} (vector store: {vector_store_service.is_available()})")

    from app.agents.orchestrator.orchestrator_agent import OrchestratorAgent
    from app.models.schemas import ChatRequest

    orch = OrchestratorAgent()
    results = []
    for query, lang, aliases, topic, aspects in GOLDEN:
        t = time.time()
        try:
            resp = await orch.process_user_query(ChatRequest(query=query))
            row = score_one(query, lang, aliases, topic, aspects, resp, (time.time() - t) * 1000)
        except Exception as exc:  # pipeline crash — all checks fail
            row = {"query": query, "expected_lang": lang, "error": str(exc),
                   **{c: False for c in CHECKS}}
            row["aspect_coverage"] = "0/2"
        results.append(row)
        flags = "".join("Y" if row.get(c) else ("~" if c == "aspect_coverage" else "n") for c in CHECKS)
        print(f"[{flags}] {query[:48]}")

    n = len(results)
    print("-" * 100)
    agg = {}
    for c in CHECKS:
        key = "aspect_pass" if c == "aspect_coverage" else c
        ok = sum(1 for r in results if r.get(key))
        agg[c] = {"pass": ok, "total": n, "rate": round(ok / n, 3)}
        print(f"{c:22} {ok}/{n} = {ok / n:.1%}")
    avg_lat = sum(r.get("latency_ms", 0) for r in results if "latency_ms" in r) / max(1, sum(1 for r in results if "latency_ms" in r))
    print(f"avg latency: {avg_lat / 1000:.1f}s per query (mode: {llm_mode})")

    out = {"mode": llm_mode, "aggregate": agg, "results": results}
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
