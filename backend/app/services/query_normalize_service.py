"""Query normalization: typo correction before NLP/retrieval.

Two layers, cheapest first:

1. Rule-based (always, offline, zero cost): each ASCII token is matched
   with difflib against a vocabulary of districts, provinces, climate
   topics and common query words. "weathe" -> "weather", "Kndy" -> "Kandy".
   Sinhala/Tamil tokens are never touched.
2. Bedrock rewrite (only when needed): if rule-based changed nothing but
   unknown tokens remain AND an LLM is available, ask it to fix spelling
   and rephrase once. Any failure falls back to the rule-based output.

Returns the normalized query plus the correction list so the pipeline can
tell the user what was interpreted ("Showing results for 'weather'").
"""

from __future__ import annotations

import logging
import re
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# Canonical English vocabulary the matcher may correct TOWARDS.
# District, town and city names are included so known places are never
# "corrected" away (e.g. "nugawela" must survive to reach the gazetteer).
_DISTRICTS = [
    "colombo", "gampaha", "kalutara", "kandy", "matale", "nuwara eliya",
    "galle", "matara", "hambantota", "jaffna", "kilinochchi", "mannar",
    "vavuniya", "mullaitivu", "batticaloa", "ampara", "trincomalee",
    "kurunegala", "puttalam", "anuradhapura", "polonnaruwa", "badulla",
    "monaragala", "ratnapura", "kegalle", "kalpitiya", "gampola", "negombo",
    "kandy", "galle", "jaffna", "colombo", "moratuwa", "kotte",
    "nugawela", "tangalle", "ella", "mirissa", "chilaw", "kuliyapitiya",
    "embilipitiya", "nugegoda", "maharagama", "dehiwala", "kesbewa",
    "homagama", "kaduwela", "avissawella", "wattala", "mirigama",
    "panadura", "horana", "beruwala", "aluthgama", "mathugama",
    "nawalapitiya", "katugastota", "kundasale", "galagedara", "akurana",
    "dambulla", "sigiriya", "galewela", "rattota", "naula",
    "hatton", "talawakelle", "kotmale", "maskeliya",
    "ambalangoda", "elpitiya", "baddegama", "habaraduwa",
    "weligama", "akuressa", "hakmana", "dikwella",
    "tissamaharama", "ambalantota", "beliatta", "lunugamvehera",
    "kinniya", "mutur", "kantale", "seruvila",
    "narammala", "pannala", "polgahawela", "alawwa", "mawathagama",
    "wennappuwa", "anamaduwa", "mundel",
    "kekirawa", "eppawala", "mihintale", "medawachchiya",
    "bandarawela", "haputale", "welimada", "mahiyanganaya", "passara",
    "wellawaya", "bibile", "buttala", "katharagama",
    "balangoda", "kuruwita", "pelmadulla", "kahawatta",
    "mawanella", "rambukkana", "warakapola", "galigamuwa",
]
_PROVINCES = [
    "western", "central", "southern", "northern", "eastern", "north western",
    "north central", "uva", "sabaragamuwa", "province",
]
_TOPICS = [
    "weather", "climate", "flood", "flooding", "drought", "cyclone",
    "landslide", "landslides", "heat", "heatwave", "rain", "rainfall",
    "monsoon", "storm", "storms", "temperature", "humidity", "wind",
    "forecast", "risk", "risks", "hazard", "hazards", "disaster",
    "preparedness", "evacuation", "alert", "alerts", "warning", "warnings",
    "water", "river", "sea", "coast", "coastal", "agriculture", "crop",
    "crops", "farming", "irrigation", "harvest",
]
_COMMON = [
    "what", "is", "the", "in", "of", "for", "and", "are", "there", "any",
    "right", "now", "today", "this", "week", "current", "currently",
    "situation", "conditions", "about", "tell", "give", "show", "how",
    "should", "will", "area", "areas", "region", "district", "city",
    "sri", "lanka", "preparation", "prepare", "affect", "affected",
    # Common English pronouns, verbs, and adjectives that must never be
    # corrected (e.g. "them" -> "the", "then" -> "the", "they" -> "the")
    "them", "they", "then", "their", "these", "those", "that", "than",
    "with", "from", "have", "been", "when", "where", "which", "while",
    "grow", "growing", "plant", "planting", "protect", "protecting",
    "suitable", "suitable", "heavy", "light", "high", "low",
    "need", "needs", "help", "want", "want", "keep", "kept",
    "make", "made", "take", "taken", "also", "both", "each",
    "very", "much", "more", "most", "some", "such", "many", "much",
    "can", "could", "would", "might", "must", "does", "doing", "done",
    "vegetables", "vegetable", "fruit", "fruits", "soil", "seeds", "seed",
    "field", "fields", "garden", "farm", "farmer", "farmers",
]

_VOCAB: set[str] = set()
for _phrase in _DISTRICTS + _PROVINCES + _TOPICS + _COMMON:
    _VOCAB.update(_phrase.split())
_VOCAB |= {"srilanka"}

_WORD_RE = re.compile(r"[A-Za-z']+")
_MIN_LEN = 4
_CUTOFF = 0.82


def _is_ascii_word(token: str) -> bool:
    return bool(token) and all("a" <= ch <= "z" or ch in "'-" for ch in token.lower())


def correct_token(token: str) -> str | None:
    """Return the vocabulary correction for one token, or None to keep it."""
    word = token.lower()
    if len(word) < _MIN_LEN or not _is_ascii_word(word):
        return None
    if word in _VOCAB:
        return None
    # Never "correct" off-topic signal words: "train" must not become
    # "rain", or the off-topic gate loses its evidence.
    from app.agents.nlp_agent.nlp_agent import NON_CLIMATE_TERMS as _blocked_terms
    if word in _blocked_terms:
        return None
    match = get_close_matches(word, _VOCAB, n=1, cutoff=_CUTOFF)
    return match[0] if match else None


def normalize_rule_based(query: str) -> tuple[str, list[tuple[str, str]]]:
    """Fix typos token-by-token. Returns (normalized, [(orig, fixed), ...])."""
    corrections: list[tuple[str, str]] = []

    def _fix(m: re.Match) -> str:
        token = m.group(0)
        fixed = correct_token(token)
        if fixed is None:
            return token
        # Preserve leading capital (e.g. "Kndy" -> "Kandy").
        if token[0].isupper():
            fixed = fixed.capitalize()
        corrections.append((token, fixed))
        return fixed

    return _WORD_RE.sub(_fix, query), corrections


def has_unknown_tokens(query: str) -> bool:
    for m in _WORD_RE.finditer(query):
        word = m.group(0).lower()
        if len(word) >= _MIN_LEN and word not in _VOCAB and correct_token(m.group(0)) is None:
            return True
    return False


async def _bedrock_rewrite(query: str) -> str | None:
    """Ask the LLM to fix spelling/rephrase. None when unavailable/failing."""
    try:
        from app.services.llm_service import llm_service
        if not llm_service.is_available():
            return None
        out = await llm_service.invoke_model(
            prompt=(
                "Fix any spelling mistakes in this climate question about Sri Lanka "
                "and return ONLY the corrected question, nothing else.\n\n"
                f"Question: {query}"
            ),
            system_prompt="You correct spelling in user questions. Output only the corrected question.",
            max_tokens=100,
            temperature=0.0,
        )
        out = (out or "").strip().strip('"')
        return out or None
    except Exception as exc:
        logger.warning("Bedrock query rewrite unavailable (%s)", exc)
        return None


async def normalize_query(query: str, use_llm: bool = True) -> tuple[str, list[tuple[str, str]], bool]:
    """Normalize a user query.

    Returns (normalized_query, corrections, llm_used). Rule-based first
    (deterministic, free); Bedrock only when nothing was corrected but
    suspicious tokens remain and an LLM is reachable.
    """
    normalized, corrections = normalize_rule_based(query)
    if corrections or not use_llm:
        return normalized, corrections, False
    if not has_unknown_tokens(query):
        return normalized, corrections, False
    rewritten = await _bedrock_rewrite(query)
    if not rewritten or rewritten == query:
        return normalized, corrections, False
    renormalized, more = normalize_rule_based(rewritten)
    return renormalized, corrections + more, True
