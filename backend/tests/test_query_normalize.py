"""Query normalization tests: typo correction without an LLM.

Run with:  venv\\Scripts\\python -m pytest tests/test_query_normalize.py -q
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import query_normalize_service as qnorm  # noqa: E402


def test_typo_weather_and_city_fixed():
    normalized, corrections = qnorm.normalize_rule_based("weathe in colomob")
    assert "weather" in normalized, normalized
    assert "colombo" in normalized, normalized
    assert ("weathe", "weather") in corrections
    assert ("colomob", "colombo") in corrections


def test_typo_district_fixed_preserving_case():
    normalized, corrections = qnorm.normalize_rule_based("Is there a flood risk in Kndy?")
    assert "Kandy" in normalized, normalized
    assert ("Kndy", "Kandy") in corrections


def test_clean_query_untouched():
    query = "Is there a flood risk in Kandy right now?"
    normalized, corrections = qnorm.normalize_rule_based(query)
    assert normalized == query
    assert corrections == []


def test_sinhala_tamil_untouched():
    for query in [
        "මහනුවර ගංවතුර අවදානමක් තිබේද?",
        "கண்டியில் வெள்ள அபாயம் உள்ளதா?",
    ]:
        normalized, corrections = qnorm.normalize_rule_based(query)
        assert normalized == query, normalized
        assert corrections == []


def test_gibberish_and_short_tokens_untouched():
    normalized, corrections = qnorm.normalize_rule_based("xyzabc qqq in a flood")
    assert "xyzabc" in normalized and "qqq" in normalized
    assert "flood" in normalized


def test_normalize_query_offline_never_uses_llm():
    normalized, corrections, llm_used = asyncio.run(
        qnorm.normalize_query("weathe in colomob", use_llm=True))
    assert llm_used is False
    assert "weather" in normalized


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
