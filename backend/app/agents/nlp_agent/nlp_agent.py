"""
NLP Agent (Query & NLP Agent) - MCP Server

Responsibilities:
- Intent detection: Identify what the user wants (risk_awareness, forecast, preparedness, etc.)
- Entity extraction: Extract location, date/time, climate topic, hazard type
- Query expansion: Add related terms to improve retrieval
- Summarization: Condense long text into concise evidence snippets

Tools exposed via MCP:
- process_query: Full NLP pipeline on user input
- extract_entities: Named Entity Recognition for climate entities
- expand_query: Query expansion for better retrieval
- summarize_text: Summarize retrieved documents

Design notes:
- The core pipeline is rule-based so the agent works with zero external
  dependencies (mirrors the orchestrator's fallback NLP but is more complete).
- If spaCy is installed, it is used to enrich location/date entity extraction.
- If the LLM is available, it is used to refine query expansion and to power
  summarization. Every LLM/spaCy path degrades gracefully to rules on failure.

Output contract (consumed by the Orchestrator + IR Agent):
    process_query -> {
        "intent": str,
        "entities": {location, date, climate_topic, hazard_type},
        "structured_query": {"original_query": str, "processed": True},
        "expanded_terms": [str, ...],
        "expanded_query": str,
    }

Port: 8101
"""

import logging

from app.mcp.base_agent_server import BaseAgentServer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static knowledge bases (kept module-level so they are built once per process)
# ---------------------------------------------------------------------------

# All 25 Sri Lanka districts + 9 provinces + common sub-regions.
# Ordered longest/most specific first so "nuwara eliya" matches before "eliya".
SRI_LANKA_LOCATIONS: list[tuple[str, str]] = [
    ("nuwara eliya",              "Nuwara Eliya, Sri Lanka"),
    ("anuradhapura",              "Anuradhapura, Sri Lanka"),
    ("polonnaruwa",               "Polonnaruwa, Sri Lanka"),
    ("trincomalee",               "Trincomalee, Sri Lanka"),
    ("hambantota",                "Hambantota, Sri Lanka"),
    ("kilinochchi",               "Kilinochchi, Sri Lanka"),
    ("mullaitivu",                "Mullaitivu, Sri Lanka"),
    ("vavuniya",                  "Vavuniya, Sri Lanka"),
    ("batticaloa",                "Batticaloa, Sri Lanka"),
    ("monaragala",                "Monaragala, Sri Lanka"),
    ("kurunegala",                "Kurunegala, Sri Lanka"),
    ("ratnapura",                 "Ratnapura, Sri Lanka"),
    ("kalpitiya",                 "Kalpitiya, Sri Lanka"),
    ("kalutara",                  "Kalutara, Sri Lanka"),
    ("gampaha",                   "Gampaha, Sri Lanka"),
    ("matale",                    "Matale, Sri Lanka"),
    ("badulla",                   "Badulla, Sri Lanka"),
    ("kegalle",                   "Kegalle, Sri Lanka"),
    ("ampara",                    "Ampara, Sri Lanka"),
    ("puttalam",                  "Puttalam, Sri Lanka"),
    ("matara",                    "Matara, Sri Lanka"),
    ("mannar",                    "Mannar, Sri Lanka"),
    ("kandy",                     "Kandy, Sri Lanka"),
    ("galle",                     "Galle, Sri Lanka"),
    ("jaffna",                    "Jaffna, Sri Lanka"),
    ("colombo",                   "Colombo, Sri Lanka"),
    # Provinces
    ("western province",          "Western Province, Sri Lanka"),
    ("central province",          "Central Province, Sri Lanka"),
    ("southern province",         "Southern Province, Sri Lanka"),
    ("northern province",         "Northern Province, Sri Lanka"),
    ("eastern province",          "Eastern Province, Sri Lanka"),
    ("north western province",    "North Western Province, Sri Lanka"),
    ("north central province",    "North Central Province, Sri Lanka"),
    ("uva province",              "Uva Province, Sri Lanka"),
    ("sabaragamuwa",              "Sabaragamuwa Province, Sri Lanka"),
    # Sub-regions / geographic features
    ("dry zone",                  "Dry Zone, Sri Lanka"),
    ("hill country",              "Central Highlands, Sri Lanka"),
    ("knuckles",                  "Matale, Sri Lanka"),
    ("horton plains",             "Nuwara Eliya, Sri Lanka"),
    ("wilpattu",                  "Anuradhapura, Sri Lanka"),
    ("yala",                      "Hambantota, Sri Lanka"),
    ("sinharaja",                 "Sinharaja, Sri Lanka"),
    ("mahaweli",                  "Mahaweli Basin, Sri Lanka"),
    ("kelani",                    "Colombo, Sri Lanka"),
    ("sri lanka",                 "Sri Lanka"),
]

# Climate topic -> keyword triggers. First match wins (dict preserves order).
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "flood":          ["flood", "flooding", "inundation", "overflow", "waterlog",
                       "flash flood", "river level", "discharge"],
    "drought":        ["drought", "dry spell", "water scarcity", "arid",
                       "low rainfall", "water shortage"],
    "heat-wave":      ["heat wave", "heatwave", "heat stress", "heat island",
                       "extreme heat", "heat index"],
    "cyclone":        ["cyclone", "hurricane", "typhoon", "tropical storm",
                       "storm surge", "wind speed"],
    "landslide":      ["landslide", "mudslide", "slope failure", "debris flow",
                       "hillside collapse"],
    "sea-level-rise": ["sea level", "coastal erosion", "shoreline erosion",
                       "tidal flooding"],
    "rain":           ["rainfall", "monsoon", "precipitation", "downpour",
                       "heavy rain", "rain"],
    "air-quality":    ["air quality", "pollution", "pm2.5", "smog",
                       "particulate", "aqi"],
    "wildfire":       ["wildfire", "forest fire", "fire risk", "bush fire",
                       "burning forest"],
    "erosion":        ["erosion", "soil erosion", "bank erosion", "sediment",
                       "topsoil loss"],
    "water-scarcity": ["groundwater", "aquifer", "water table",
                       "drinking water shortage", "water stress"],
    "agriculture":    ["crop failure", "crop damage", "harvest loss",
                       "farming climate", "climate agriculture", "drought crop",
                       "flood crop", "monsoon farming", "yield decline",
                       "agriculture", "irrigation"],
    "temperature":    ["temperature", "hot", "warming", "cold", "climate change"],
    "storm":          ["storm", "thunderstorm", "lightning", "gale"],
}

# Intent -> keyword triggers. Evaluated in priority order (most specific first).
INTENT_KEYWORDS: list[tuple[str, list[str]]] = [
    ("preparedness",  ["prepare", "should i", "what to do", "how to", "advice",
                       "protect", "ready", "precaution", "safety", "mitigate"]),
    ("forecast",      ["forecast", "predict", "next week", "tomorrow", "upcoming",
                       "this week", "will it", "expected", "outlook"]),
    ("trend_analysis",["history", "trend", "past", "change over", "last year",
                       "over the years", "historical", "compared to"]),
    ("risk_awareness",["risk", "danger", "threat", "vulnerable", "hazard",
                       "impact", "affected", "damage"]),
]

# Off-topic terms that should never be treated as climate questions even if
# a Sri Lanka place name is present (e.g. "Kandy train timetable").
NON_CLIMATE_TERMS: list[str] = [
    "price of", "cost of", "how much does", "how much is",
    "train", "bus", "flight", "timetable", "schedule", "ticket",
    "president", "prime minister", "minister", "government",
    "election", "vote", "parliament", "political",
    "recipe", "cook", "restaurant", "hotel", "tourist",
    "cricket", "football", "sport", "match", "score",
    "school", "university", "exam", "admission",
    "salary", "job", "vacancy", "hire",
    "population", "history of", "capital of",
]

# Any of these words confirms a query is climate-related.
CLIMATE_TERMS: tuple[str, ...] = (
    "climate", "weather", "flood", "drought", "rain", "rainfall", "monsoon",
    "storm", "cyclone", "heat", "temperature", "humidity", "wind", "agriculture",
    "environment", "pollution", "landslide", "water", "irrigation", "sea level",
    "forecast", "disaster", "preparedness", "risk", "erosion", "wildfire",
    "air quality", "hazard",
)

# Query-expansion synonym map — deterministic term expansion for better recall.
EXPANSION_SYNONYMS: dict[str, list[str]] = {
    "flood":       ["flooding", "inundation", "river overflow", "flash flood"],
    "drought":     ["dry spell", "water scarcity", "rainfall deficit"],
    "heat-wave":   ["extreme heat", "heat stress", "high temperature"],
    "cyclone":     ["tropical storm", "storm surge", "high winds"],
    "landslide":   ["mudslide", "slope failure", "debris flow"],
    "rain":        ["rainfall", "precipitation", "monsoon"],
    "air-quality": ["pm2.5", "air pollution", "aqi"],
    "sea-level-rise": ["coastal flooding", "shoreline erosion", "storm surge"],
    "wildfire":    ["forest fire", "bushfire", "fire risk"],
    "erosion":     ["soil erosion", "sediment loss"],
    "agriculture": ["crops", "harvest", "farming", "irrigation"],
}

# Simple relative-date vocabulary for lightweight date extraction (no spaCy needed).
DATE_KEYWORDS: tuple[str, ...] = (
    "today", "tomorrow", "yesterday", "tonight", "this week", "next week",
    "this month", "next month", "this year", "next year", "this weekend",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
)


class NLPAgent(BaseAgentServer):
    """NLP Agent for intent detection, entity extraction, and query processing."""

    def __init__(self):
        super().__init__(
            name="nlp_agent",
            port=8101,
            description="Handles intent detection, entity extraction, query expansion and summarization",
        )

        # spaCy is optional. If present, it enriches entity extraction; if not,
        # rule-based extraction is used. Loaded lazily on first use.
        self._spacy_nlp = None
        self._spacy_loaded = False

        # Register tools
        self.register_tool(
            "process_query",
            self.process_query,
            "Full NLP processing: intent detection + entity extraction + query structuring",
        )
        self.register_tool(
            "extract_entities",
            self.extract_entities,
            "Extract named entities (location, date, topic, hazard) from text",
        )
        self.register_tool(
            "expand_query",
            self.expand_query,
            "Expand query with related terms for better retrieval",
        )
        self.register_tool(
            "summarize_text",
            self.summarize_text,
            "Summarize long text into concise snippets",
        )

    # =========================================================================
    # Optional spaCy loader
    # =========================================================================

    def _get_spacy(self):
        """
        Lazily load the spaCy English model. Returns the nlp object or None.
        Cached so the (expensive) load happens at most once per process.
        """
        if self._spacy_loaded:
            return self._spacy_nlp

        self._spacy_loaded = True
        try:
            import spacy
            self._spacy_nlp = spacy.load("en_core_web_sm")
            logger.info("NLP Agent: spaCy model 'en_core_web_sm' loaded for NER")
        except Exception as exc:  # ImportError or model-not-downloaded
            logger.info(
                "NLP Agent: spaCy unavailable (%s) — using rule-based entity extraction",
                exc,
            )
            self._spacy_nlp = None
        return self._spacy_nlp

    # =========================================================================
    # Tool: process_query
    # =========================================================================

    async def process_query(self, arguments: dict) -> dict:
        """
        Full NLP pipeline on user input.

        Input:
            - query (str): User's raw query text
            - location (str, optional): Provided location field
            - user_type (str, optional): Type of user

        Output:
            - intent (str)
            - entities (dict): {location, date, climate_topic, hazard_type}
            - structured_query (dict)
            - expanded_terms (list)
            - expanded_query (str)
        """
        query = (arguments.get("query") or "").strip()
        location_field = arguments.get("location")

        if not query:
            return {
                "intent": "general_climate_query",
                "entities": {},
                "structured_query": {"original_query": "", "processed": False},
                "expanded_terms": [],
                "expanded_query": "",
            }

        query_lower = query.lower()

        # 1. Off-topic guard — mirror the orchestrator's blocklist so a location
        #    match alone (e.g. "Kandy train times") never produces climate results.
        if any(term in query_lower for term in NON_CLIMATE_TERMS):
            return {
                "intent": "non_climate",
                "entities": {},
                "structured_query": {"original_query": query, "processed": True},
                "expanded_terms": [],
                "expanded_query": query,
            }

        # 2. Entity extraction (rules + optional spaCy)
        entities = self._extract_entities_impl(query, location_field)

        # 3. Intent detection
        intent = self._classify_intent(query_lower)

        # 4. Query expansion (deterministic synonyms + optional LLM refinement)
        expansion = await self._expand_query_impl(query, entities)

        return {
            "intent": intent,
            "entities": entities,
            "structured_query": {"original_query": query, "processed": True},
            "expanded_terms": expansion["expanded_terms"],
            "expanded_query": expansion["expanded_query"],
        }

    # =========================================================================
    # Tool: extract_entities
    # =========================================================================

    async def extract_entities(self, arguments: dict) -> dict:
        """
        Extract named entities from text.

        Input:
            - text (str): Text to extract entities from
            - location (str, optional): Explicit location hint

        Output:
            - entities (dict): {location, date, climate_topic, hazard_type}
        """
        text = arguments.get("text") or arguments.get("query") or ""
        location_hint = arguments.get("location")
        entities = self._extract_entities_impl(text, location_hint)
        return {"entities": entities}

    def _extract_entities_impl(self, text: str, location_hint=None) -> dict:
        """
        Core entity extraction.

        Strategy:
        - Location: keyword gazetteer (query text preferred) + spaCy GPE/LOC.
        - Date: relative-date keywords + spaCy DATE labels.
        - Climate topic + hazard type: keyword matching against TOPIC_KEYWORDS.
        """
        text_lower = text.lower()

        # --- Location ---
        detected_location = None
        for keyword, canonical in SRI_LANKA_LOCATIONS:
            if keyword in text_lower:
                detected_location = canonical
                break

        # --- Date (rule-based) ---
        dates: list[str] = [kw for kw in DATE_KEYWORDS if kw in text_lower]

        # --- spaCy enrichment (optional) ---
        nlp = self._get_spacy()
        if nlp is not None:
            try:
                doc = nlp(text)
                for ent in doc.ents:
                    if ent.label_ in ("GPE", "LOC") and not detected_location:
                        detected_location = ent.text
                    elif ent.label_ == "DATE" and ent.text.lower() not in dates:
                        dates.append(ent.text)
            except Exception as exc:
                logger.warning("NLP Agent: spaCy NER failed: %s", exc)

        # Fall back to the explicit location field last.
        if not detected_location and location_hint:
            detected_location = str(location_hint)

        # --- Climate topic + hazard type ---
        climate_topic = None
        hazard_type = None
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                climate_topic = topic
                hazard_type = topic
                break

        entities: dict = {}
        if detected_location:
            entities["location"] = detected_location
        if dates:
            # De-duplicate while preserving order
            entities["date"] = list(dict.fromkeys(dates))
        if climate_topic:
            entities["climate_topic"] = climate_topic
            entities["hazard_type"] = hazard_type

        return entities

    # =========================================================================
    # Tool: expand_query
    # =========================================================================

    async def expand_query(self, arguments: dict) -> dict:
        """
        Expand a query with related terms for better retrieval.

        Input:
            - query (str): Original query
            - entities (dict, optional): Pre-extracted entities

        Output:
            - expanded_terms (list)
            - expanded_query (str)
        """
        query = arguments.get("query", "")
        entities = arguments.get("entities")
        if entities is None:
            entities = self._extract_entities_impl(query, arguments.get("location"))
        return await self._expand_query_impl(query, entities)

    async def _expand_query_impl(self, query: str, entities: dict) -> dict:
        """
        Build expansion terms deterministically from the detected topic/location,
        then (best-effort) ask the LLM for a few more domain synonyms.
        """
        expanded_terms: list[str] = []

        # Deterministic synonyms from the detected climate topic
        topic = entities.get("climate_topic")
        if topic and topic in EXPANSION_SYNONYMS:
            expanded_terms.extend(EXPANSION_SYNONYMS[topic])

        # Include the location token so retrieval can match location-tagged docs
        location = entities.get("location")
        if location:
            expanded_terms.append(str(location))

        # Optional LLM refinement — never fatal if the LLM is unavailable
        try:
            from app.services.llm_service import llm_service

            if llm_service.is_available() and llm_service.get_provider() != "mock":
                prompt = (
                    "Give 3 to 5 short climate/weather search keywords related to this "
                    f'query, comma-separated, no explanation:\n"{query}"'
                )
                response = await llm_service.invoke_model(
                    prompt=prompt,
                    system_prompt="Return only a comma-separated list of short keywords.",
                    max_tokens=60,
                    temperature=0.2,
                )
                for term in response.split(","):
                    cleaned = term.strip().strip(".").lower()
                    if cleaned and len(cleaned) < 40 and cleaned not in expanded_terms:
                        expanded_terms.append(cleaned)
        except Exception as exc:
            logger.warning("NLP Agent: LLM query expansion skipped: %s", exc)

        # De-duplicate, drop terms already present verbatim in the query
        query_lower = query.lower()
        final_terms: list[str] = []
        for term in expanded_terms:
            if term.lower() not in query_lower and term not in final_terms:
                final_terms.append(term)

        expanded_query = query
        if final_terms:
            expanded_query = f"{query} {' '.join(final_terms)}"

        return {"expanded_terms": final_terms, "expanded_query": expanded_query}

    # =========================================================================
    # Tool: summarize_text
    # =========================================================================

    async def summarize_text(self, arguments: dict) -> dict:
        """
        Summarize long text into concise snippets.

        Input:
            - text (str): Long text to summarize
            - max_length (int, optional): Approximate max words in the summary

        Output:
            - summary (str)
        """
        text = (arguments.get("text") or "").strip()
        max_length = int(arguments.get("max_length", 60) or 60)

        if not text:
            return {"summary": ""}

        # Prefer LLM summarization when a real provider is configured.
        try:
            from app.services.llm_service import llm_service

            if llm_service.is_available() and llm_service.get_provider() != "mock":
                prompt = (
                    f"Summarize the following climate/weather text in at most "
                    f"{max_length} words. Preserve numbers, locations and dates.\n\n{text}"
                )
                summary = await llm_service.invoke_model(
                    prompt=prompt,
                    system_prompt="You are a precise climate information summarizer.",
                    max_tokens=max(120, max_length * 4),
                    temperature=0.2,
                )
                if summary and not summary.startswith("[MOCK RESPONSE"):
                    return {"summary": summary.strip()}
        except Exception as exc:
            logger.warning("NLP Agent: LLM summarization failed, using extractive fallback: %s", exc)

        # Extractive fallback: keep leading sentences up to the word budget.
        return {"summary": self._extractive_summary(text, max_length)}

    @staticmethod
    def _extractive_summary(text: str, max_words: int) -> str:
        """Simple extractive summary — first sentences up to the word budget."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        summary_words: list[str] = []
        for sentence in sentences:
            words = sentence.split()
            if not words:
                continue
            if len(summary_words) + len(words) > max_words and summary_words:
                break
            summary_words.extend(words)
        summary = " ".join(summary_words).strip()
        if not summary:
            summary = " ".join(text.split()[:max_words])
        return summary

    # =========================================================================
    # Intent classification helper
    # =========================================================================

    @staticmethod
    def _classify_intent(query_lower: str) -> str:
        """Keyword-based intent classification, evaluated in priority order."""
        for intent, keywords in INTENT_KEYWORDS:
            if any(kw in query_lower for kw in keywords):
                return intent
        return "general_climate_query"


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = NLPAgent()
    agent.run()
