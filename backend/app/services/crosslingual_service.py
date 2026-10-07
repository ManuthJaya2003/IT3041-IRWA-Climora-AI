"""Cross-lingual retrieval bridge (offline, zero dependencies).

Sinhala/Tamil queries are expanded with the English terms the document
corpus is written in, using the same gazetteers the NLP agent uses. This
lets lexical (TF-IDF) and English-centric neural (Titan) embeddings match
English documents from non-English queries.

Design note for examiners: this is deterministic dictionary-based
translation for *retrieval only* (answers are still generated in the
user's language). A neural multilingual embedding model
(e.g. paraphrase-multilingual-MiniLM, 384-dim, drop-in for this index)
can replace the TF-IDF path later behind the same function.
"""

from app.agents.nlp_agent.nlp_agent import (
    SRI_LANKA_LOCATIONS,
    SRI_LANKA_LOCATION_STEMS,
    TOPIC_KEYWORDS,
)

# Longest-first so "nuwara eliya" wins over shorter fragments and full
# native names win over their stems.
_LOC_ORDERED: list[tuple[str, str]] = sorted(
    SRI_LANKA_LOCATIONS, key=lambda kv: len(kv[0]), reverse=True
)


def _build_topic_bridge() -> dict[str, list[str]]:
    """Map every non-English topic keyword to English retrieval terms."""
    bridge: dict[str, list[str]] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        english = [k for k in keywords if k.isascii()][:3]
        extra = [topic.replace("-", " "), *english[:2]]
        for keyword in keywords:
            if not keyword.isascii() and keyword not in bridge:
                bridge[keyword] = extra
    return bridge


_TOPIC_BRIDGE = _build_topic_bridge()


def to_english_query(text: str) -> str:
    """Append English equivalents for any Sinhala/Tamil location/topic terms.

    Pure-English input is returned unchanged. The original text is always
    kept — English terms are appended so nothing is lost in translation.
    """
    if not text or text.isascii():
        return text
    lowered = text.lower()
    extra: list[str] = []
    matched_location = False

    for keyword, canonical in _LOC_ORDERED:
        if keyword and keyword in lowered:
            matched_location = True
            district = canonical.split(",")[0].strip()
            if district and district.lower() not in lowered:
                extra.append(district)

    if not matched_location:
        # Inflected Tamil forms (e.g. யாழ்ப்பாணத்தில்) — see
        # SRI_LANKA_LOCATION_STEMS in the NLP agent.
        for stem, canonical in SRI_LANKA_LOCATION_STEMS:
            if stem and stem in lowered:
                district = canonical.split(",")[0].strip()
                if district and district.lower() not in lowered:
                    extra.append(district)

    for keyword, terms in _TOPIC_BRIDGE.items():
        if keyword in lowered:
            extra.extend(t for t in terms if t.lower() not in lowered)

    if not extra:
        return text
    seen: set[str] = set()
    tail = [w for w in extra if not (w in seen or seen.add(w))]
    return f"{text} {' '.join(tail)}"
