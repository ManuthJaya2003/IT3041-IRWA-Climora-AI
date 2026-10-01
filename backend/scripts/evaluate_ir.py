"""IR evaluation: location/topic extraction accuracy + retrieval hit rate.

Golden set covers English, Sinhala and Tamil queries against the seeded
FAISS store. Runs fully offline (rule-based NLP + local vector store).

Usage:  python scripts/evaluate_ir.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.nlp_agent.nlp_agent import NLPAgent
from app.services.vector_store_service import vector_store_service

# (query, expected_location_substring, expected_topic)
GOLDEN = [
    # English
    ("What is the current weather in Colombo?", "Colombo", "temperature"),
    ("Is there a flood risk in Kandy right now?", "Kandy", "flood"),
    ("Assess drought risk for the Dry Zone in Sri Lanka", "Dry Zone", "drought"),
    ("Are there landslide risks in Nuwara Eliya?", "Nuwara Eliya", "landslide"),
    ("What is the cyclone risk in Trincomalee?", "Trincomalee", "cyclone"),
    ("What is the drought situation in Jaffna?", "Jaffna", "drought"),
    ("Flooding in Galle during monsoon season?", "Galle", "flood"),
    ("Heat wave conditions in Colombo city?", "Colombo", "heat-wave"),
    # Sinhala
    ("කොළඹ මෝසම් වර්ෂාවට සූදානම් වන්නේ කෙසේද?", "Colombo", "rain"),
    ("අනුරාධපුරයේ නියං අවදානම තක්සේරු කරන්න", "Anuradhapura", "drought"),
    ("මහනුවර ගංවතුර අවදානමක් තිබේද?", "Kandy", "flood"),
    ("යාපනයේ නියඟ තත්ත්වය කුමක්ද?", "Jaffna", "drought"),
    # Tamil
    ("நுவரெலியாவில் நிலச்சரிவு அபாயம் உள்ளதா?", "Nuwara Eliya", "landslide"),
    ("திருகோணமலையில் சூறாவளி ஆபத்து என்ன?", "Trincomalee", "cyclone"),
    ("கொழும்பில் வானிலை எப்படி?", "Colombo", "temperature"),
    ("கண்டியில் வெள்ள அபாயம் உள்ளதா?", "Kandy", "flood"),
]


async def main() -> int:
    nlp = NLPAgent()
    await vector_store_service.initialize()
    store_ok = vector_store_service.is_available()

    loc_ok = topic_ok = 0
    ret_ok = 0
    ret_n = 0
    rows = []

    for query, exp_loc, exp_topic in GOLDEN:
        entities = nlp._extract_entities_impl(query, None)
        got_loc = entities.get("location", "") or "-"
        got_topic = entities.get("climate_topic", "") or "-"
        loc_hit = exp_loc.lower() in got_loc.lower()
        topic_hit = exp_topic.lower() == got_topic.lower()
        loc_ok += loc_hit
        topic_ok += topic_hit

        ret = "-"
        if store_ok and got_loc != "-":
            search = query if got_loc.lower() not in query.lower() else f"{query} {got_loc}"
            try:
                docs = await vector_store_service.query_similar(query_text=search, top_k=3)
            except Exception:
                docs = []
            if docs:
                ret_n += 1

                def _text(d: dict) -> str:
                    meta = d.get("metadata") or {}
                    return " ".join([
                        str(d.get("content", "")),
                        str(meta.get("location", "")),
                        str(meta.get("topic", "")),
                    ]).lower()

                hit = any(exp_loc.lower() in _text(d) or exp_topic.lower() in _text(d) for d in docs)
                ret_ok += hit
                ret = "HIT" if hit else "miss"
            else:
                ret = "no-docs"
        rows.append((query[:42], got_loc[:28], "Y" if loc_hit else "n",
                     got_topic[:12], "Y" if topic_hit else "n", ret))

    n = len(GOLDEN)
    print(f"{'query':42} | {'location':28} | L | {'topic':12} | T | retrieval")
    print("-" * 110)
    for r in rows:
        print(f"{r[0]:42} | {r[1]:28} | {r[2]} | {r[3]:12} | {r[4]} | {r[5]}")
    print("-" * 110)
    print(f"location accuracy: {loc_ok}/{n} = {loc_ok / n:.1%}")
    print(f"topic accuracy:    {topic_ok}/{n} = {topic_ok / n:.1%}")
    if ret_n:
        print(f"retrieval top-3 hit rate: {ret_ok}/{ret_n} = {ret_ok / ret_n:.1%} (vector store: {store_ok})")
    else:
        print("retrieval: SKIPPED (vector store unavailable or empty — run the seed script first)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
