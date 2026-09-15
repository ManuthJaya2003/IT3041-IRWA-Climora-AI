"""
Information Retrieval Agent - MCP Server

Responsibilities:
- Search approved/trusted climate data sources
- Retrieve relevant documents, articles, and data
- Rank results by relevance and quality
- Return evidence with metadata (source, date, reliability)

Tools exposed via MCP:
- retrieve_documents: Main retrieval pipeline (semantic search + web sources)
- search_sources: Search specific pre-approved sources
- index_document: Index a new document into the vector store

Data Sources integrated:
- FAISS local vector store (for indexed climate documents)
- Weather APIs (OpenWeatherMap, Open-Meteo)
- Government climate data (NOAA, DMC Sri Lanka, etc.)
- News and research sources

Tech:
- FAISS for vector similarity search
- Embeddings via sentence-transformers or LLM
- httpx for API calls to external sources

Port: 8102
"""

import asyncio
import logging
import time
import uuid
import httpx
from app.mcp.base_agent_server import BaseAgentServer
from app.config import settings

logger = logging.getLogger(__name__)

# Default coordinates used only if geocoding fails and no location was given at all.
DEFAULT_LOCATION_NAME = "Colombo, Sri Lanka"
DEFAULT_LATITUDE = 6.9271
DEFAULT_LONGITUDE = 79.8612
DRY_ZONE_LOCATION_NAME = "Dry Zone, Sri Lanka"
DRY_ZONE_LATITUDE = 8.3114
DRY_ZONE_LONGITUDE = 80.4037
CLIMATE_QUERY_TERMS = (
    "climate", "weather", "flood", "drought", "rain", "rainfall", "monsoon",
    "storm", "cyclone", "heat", "temperature", "humidity", "wind", "agriculture",
    "environment", "pollution", "landslide", "water", "irrigation", "sea level",
    "forecast", "disaster", "preparedness", "risk",
)

# Approximate location aliases used for fuzzy matching during FAISS result filtering.
# Maps canonical names / provinces to their constituent place tokens.
LOCATION_ALIASES: dict[str, list[str]] = {
    "western province": ["colombo", "gampaha", "kalutara", "western"],
    "central province": ["kandy", "matale", "nuwara eliya", "central"],
    "southern province": ["galle", "matara", "hambantota", "southern"],
    "northern province": ["jaffna", "kilinochchi", "mannar", "vavuniya", "mullaitivu", "northern"],
    "eastern province": ["trincomalee", "batticaloa", "ampara", "eastern"],
    "north western province": ["kurunegala", "puttalam", "north western"],
    "north central province": ["anuradhapura", "polonnaruwa", "north central"],
    "uva province": ["badulla", "monaragala", "uva"],
    "sabaragamuwa province": ["ratnapura", "kegalle", "sabaragamuwa"],
    "colombo": ["colombo", "western"],
    "kandy": ["kandy", "central"],
    "galle": ["galle", "southern"],
    "jaffna": ["jaffna", "northern"],
    "sri lanka": ["sri lanka", "ceylon", "lk"],
}

# Simple in-memory TTL cache for external API results.
# Structure: { cache_key: (timestamp, result) }
_api_cache: dict[str, tuple[float, object]] = {}
API_CACHE_TTL_SECONDS = 600  # 10 minutes


def _cache_get(key: str):
    """Return cached value if still fresh, else None."""
    entry = _api_cache.get(key)
    if entry and (time.monotonic() - entry[0]) < API_CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(key: str, value):
    """Store value in cache with current timestamp."""
    _api_cache[key] = (time.monotonic(), value)


async def _http_get_with_retry(
    url: str,
    params: dict,
    timeout: float = 5.0,
    retries: int = 2,
    backoff: float = 0.5,
) -> httpx.Response | None:
    """
    Perform a GET request with exponential-backoff retries.

    Returns the Response on success, or None if all attempts fail.
    """
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp
                logger.warning(
                    "HTTP %s from %s (attempt %d/%d)",
                    resp.status_code, url, attempt + 1, retries + 1,
                )
        except httpx.TimeoutException:
            logger.warning("Timeout calling %s (attempt %d/%d)", url, attempt + 1, retries + 1)
        except httpx.RequestError as exc:
            logger.warning("Request error calling %s: %s (attempt %d/%d)", url, exc, attempt + 1, retries + 1)
        except Exception as exc:
            logger.warning("Unexpected error calling %s: %s (attempt %d/%d)", url, exc, attempt + 1, retries + 1)

        if attempt < retries:
            await asyncio.sleep(backoff * (2 ** attempt))

    return None


def _location_matches(requested: str, document_location: str) -> bool:
    """
    Fuzzy / hierarchical location match.

    Returns True when:
    - requested name is a substring of document_location (original exact check), OR
    - any alias token for the requested location appears in document_location, OR
    - the document_location tokens appear as aliases of the requested location.

    This prevents a query for "Western Province" from discarding a document
    tagged "Colombo, Sri Lanka", since Colombo is in the Western Province.
    """
    req_lower = requested.lower().strip()
    doc_lower = document_location.lower().strip()

    if not req_lower or not doc_lower:
        return True  # No location constraint — include document

    # Direct substring match
    req_base = req_lower.split(",")[0].strip()
    if req_base in doc_lower:
        return True

    # Check if requested location expands to aliases that match the document
    for canonical, tokens in LOCATION_ALIASES.items():
        if req_base in canonical or canonical in req_base:
            if any(token in doc_lower for token in tokens):
                return True

    # Check if document location is an alias of the requested location
    for canonical, tokens in LOCATION_ALIASES.items():
        if any(token in doc_lower for token in tokens):
            if req_base in canonical or any(token in req_base for token in tokens):
                return True

    return False


class IRAgent(BaseAgentServer):
    """Information Retrieval Agent for searching and retrieving climate evidence."""

    def __init__(self):
        super().__init__(
            name="ir_agent",
            port=8102,
            description="Searches approved sources and retrieves relevant climate documents/data",
        )

        # Register tools for MCP Orchestrator discovery
        self.register_tool(
            "retrieve_documents",
            self.retrieve_documents,
            "Main retrieval: semantic search in vector store + external source search",
        )
        self.register_tool(
            "search_sources",
            self.search_sources,
            "Search specific pre-approved climate data sources",
        )
        self.register_tool(
            "index_document",
            self.index_document,
            "Index a new document into the FAISS vector store",
        )

        # IMPORTANT: when this agent runs standalone (python -m app.agents.ir_agent.ir_agent),
        # it's a separate process from the orchestrator's main.py - so the shared
        # vector_store_service/embedding_service singletons here start uninitialized
        # unless we initialize them ourselves on startup. Without this, FAISS queries
        # silently return [] with no error.
        self._app.add_event_handler("startup", self._initialize_services)

    async def _initialize_services(self):
        """
        Initialize the embedding and vector store services this agent depends on.

        Tries sentence-transformers first for high-quality local embeddings.
        Falls back to the configured EmbeddingService (Bedrock Titan or TF-IDF).
        """
        from app.services.embedding_service import embedding_service
        from app.services.vector_store_service import vector_store_service

        # Attempt to upgrade to sentence-transformers for better semantic quality
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("all-MiniLM-L6-v2")

            # Monkey-patch embed_text so the vector store uses real neural embeddings
            def _st_embed(text: str) -> list[float]:
                return _st_model.encode(text, normalize_embeddings=True).tolist()

            embedding_service.embed_text = _st_embed
            embedding_service._available = True
            embedding_service._use_bedrock = False
            logger.info("Embedding service upgraded to sentence-transformers (all-MiniLM-L6-v2)")
        except ImportError:
            logger.info(
                "sentence-transformers not installed — using configured EmbeddingService "
                "(Bedrock Titan or TF-IDF fallback)"
            )

        await embedding_service.initialize()
        await vector_store_service.initialize()

    async def retrieve_documents(self, arguments: dict) -> dict:
        """
        Main document retrieval pipeline.

        Input:
            - structured_query (dict): Structured query from NLP agent
            - entities (dict): Extracted entities (location, topic, etc.)
            - top_k (int): Number of results to return (default 5)

        Output:
            - documents (list): Retrieved documents with metadata
              Each doc: {source_name, url, snippet, content, reliability_score, retrieved_at}
        """
        from app.services.vector_store_service import vector_store_service

        # Extract structured parameters from incoming payload
        structured_query = arguments.get("structured_query", {})
        query = (
            structured_query.get("original_query", "")
            or arguments.get("query", "")
        )
        entities = arguments.get("entities", {})
        top_k = arguments.get("top_k", 5)

        if not self._is_climate_query(query, entities):
            return {
                "documents": [],
                "message": "No climate-related evidence was retrieved for this query.",
            }

        requested_location = self._requested_location(query, entities)

        # Build enhanced search query string from extracted NLP entities
        search_parts = [query]
        if entities.get("location"):
            search_parts.append(str(entities["location"]))
        if entities.get("climate_topic"):
            search_parts.append(str(entities["climate_topic"]))
        if entities.get("hazard_type"):
            search_parts.append(str(entities["hazard_type"]))

        search_query = " ".join([p for p in search_parts if p]).strip()

        # Budget split: reserve half the slots for live API data, half for FAISS.
        # This ensures current readings are always represented alongside indexed docs.
        live_budget = max(1, top_k // 2)
        faiss_budget = top_k - live_budget

        # Step 1: Query External APIs (OpenWeatherMap & Open-Meteo) for live readings
        external_results = await self._search_external_sources(query, entities)
        live_results = external_results[:live_budget]

        # Step 2: Query FAISS Local Vector Store for semantically similar documents
        faiss_documents = []
        seen_content: set[str] = set()   # dedup key: first 120 chars of content
        try:
            faiss_results = await vector_store_service.query_similar(
                query_text=search_query or "climate risk",
                top_k=faiss_budget * 3  # Over-fetch to account for location filtering
            )

            for r in faiss_results:
                if len(faiss_documents) >= faiss_budget:
                    break
                metadata = r.get("metadata", {})
                document = {
                    "source_name": metadata.get("source", "FAISS Local Store"),
                    "url": r.get("url", metadata.get("url", "")),
                    "content": r.get("content", ""),
                    "snippet": r.get("content", "")[:300],
                    "reliability_score": r.get("score", 0.85),
                    "topic": metadata.get("topic", "climate"),
                    "location": metadata.get("location", ""),
                    "date": metadata.get("date", "live")
                }
                source_name = document["source_name"].strip().lower()
                if source_name == "test":
                    continue
                # Fuzzy location filter — uses alias expansion instead of exact substring
                if requested_location and document["location"]:
                    if not _location_matches(requested_location, str(document["location"])):
                        continue
                # Deduplicate — skip if same content was already included
                content_key = document["content"][:120].strip()
                if content_key in seen_content:
                    continue
                seen_content.add(content_key)
                faiss_documents.append(document)
        except Exception as exc:
            logger.warning("FAISS query failed: %s", exc)

        # Combine: live results first (higher priority), then FAISS
        documents = live_results + faiss_documents
        return {"documents": documents[:top_k] if documents else []}

    async def search_sources(self, arguments: dict) -> dict:
        """
        Search specific pre-approved sources.

        Input:
            - query (str): Search query
            - sources (list): Which sources to search (e.g., ["open_weather", "open_meteo"])
            - location (str): Location name to query

        Output:
            - results (list): Search results from specified sources
        """
        sources = arguments.get("sources", ["open_weather", "open_meteo"])
        location = arguments.get("location", DEFAULT_LOCATION_NAME)
        query = arguments.get("query", "")

        # Reuse the shared helper, but filter results to only the requested sources
        # so callers still get the named-source granularity they asked for.
        entities = {"location": location}
        all_results = await self._search_external_sources(query or location, entities)

        if "all" in sources:
            return {"results": all_results}

        # Map source names to the requested filter tokens
        source_filter_map = {
            "open_weather": "openweathermap",
            "open_meteo": "open-meteo",
        }
        filtered = []
        for result in all_results:
            src_name = result.get("source_name", "").lower()
            for token, api_label in source_filter_map.items():
                if token in sources and api_label in src_name:
                    filtered.append(result)
                    break

        return {"results": filtered}

    async def index_document(self, arguments: dict) -> dict:
        """
        Index a new document into the vector store.

        Input:
            - content (str): Document text content
            - metadata (dict): Document metadata (source, date, topic, etc.)

        Output:
            - indexed (bool): Success status
            - document_id (str): ID of the indexed document
        """
        from app.services.vector_store_service import vector_store_service

        content = arguments.get("content", "")
        metadata = arguments.get("metadata", {})

        if not content:
            return {"indexed": False, "error": "Content is required for indexing"}

        doc_id = str(uuid.uuid4())

        try:
            # Generate embedding and upsert into FAISS with metadata
            await vector_store_service.add_documents(
                [content],
                [metadata],
                [doc_id]
            )
            return {
                "indexed": True,
                "document_id": doc_id
            }
        except Exception as e:
            logger.warning("Failed to index document: %s", e)
            return {
                "indexed": False,
                "error": f"Failed to index document: {str(e)}"
            }

    async def _geocode_location(self, location_name: str) -> tuple[float, float, str]:
        """
        Resolve a free-text location name to (latitude, longitude, resolved_name)
        using Open-Meteo's free geocoding API (no API key required).

        Falls back to the default location's coordinates if geocoding fails or
        no location name was provided, so callers always get usable coordinates.
        Results are cached for API_CACHE_TTL_SECONDS to avoid redundant lookups.
        """
        if not location_name:
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_LOCATION_NAME

        if "dry zone" in location_name.lower():
            return DRY_ZONE_LATITUDE, DRY_ZONE_LONGITUDE, DRY_ZONE_LOCATION_NAME

        cache_key = f"geocode:{location_name.lower().strip()}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        resp = await _http_get_with_retry(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location_name, "count": 1},
        )
        if resp is not None:
            results = resp.json().get("results") or []
            if results:
                place = results[0]
                resolved_name = ", ".join(
                    filter(None, [place.get("name"), place.get("country")])
                ) or location_name
                result = (place["latitude"], place["longitude"], resolved_name)
                _cache_set(cache_key, result)
                return result

        logger.warning("Geocoding failed for '%s', falling back to default location", location_name)
        return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_LOCATION_NAME

    def _requested_location(self, query: str, entities: dict) -> str:
        """Return an explicit query location, falling back to the supplied entity."""
        location = entities.get("location", "")
        if isinstance(location, list):
            location = location[0] if location else ""

        query_lower = query.lower()
        if "dry zone" in query_lower:
            return DRY_ZONE_LOCATION_NAME
        if not location and "colombo" in query_lower:
            return "Colombo, Sri Lanka"
        return str(location or "")

    def _is_climate_query(self, query: str, entities: dict) -> bool:
        """Reject unrelated questions before semantic search returns arbitrary climate data."""
        if entities.get("climate_topic") or entities.get("hazard_type"):
            return True
        query_lower = query.lower()
        return any(term in query_lower for term in CLIMATE_QUERY_TERMS)

    async def _query_open_weather(self, location: str) -> dict | None:
        """
        Fetch current weather details from OpenWeatherMap API with caching.

        Uses settings.openweather_api_key configured in .env file.
        """
        api_key = settings.openweather_api_key
        if not api_key:
            return None

        cache_key = f"owm:{location.lower().strip()}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        resp = await _http_get_with_retry(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": location, "appid": api_key, "units": "metric"},
        )
        if resp is None:
            logger.warning("OpenWeatherMap API returned no response for location '%s'", location)
            return None

        data = resp.json()
        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]

        content_str = (
            f"Current weather in {location}: {weather_desc}, Temperature: {temp}°C, "
            f"Humidity: {humidity}%, Wind Speed: {wind_speed} m/s."
        )
        result = {
            "source_name": "OpenWeatherMap API",
            "url": f"https://openweathermap.org/city/{data.get('id', '')}",
            "content": content_str,
            "snippet": content_str,
            "reliability_score": 0.95,
            "topic": "current_weather",
            "location": location,
            "date": "live"
        }
        _cache_set(cache_key, result)
        return result

    async def _search_external_sources(self, query: str, entities: dict) -> list:
        """
        Query all external climate and weather APIs (OpenWeatherMap & Open-Meteo).
        Results are cached per location for API_CACHE_TTL_SECONDS.
        """
        results = []
        location = self._requested_location(query, entities)

        # Do not silently attach Colombo weather to a region-free question.
        if not location:
            return results

        loc_str = str(location)

        # 1. Fetch live data from OpenWeatherMap API
        owm_data = await self._query_open_weather(loc_str)
        if owm_data:
            results.append(owm_data)

        # 2. Resolve loc_str to real coordinates before calling Open-Meteo, so the
        #    forecast actually matches the requested location instead of always
        #    returning Colombo's weather.
        latitude, longitude, resolved_name = await self._geocode_location(loc_str)

        # 3. Fetch live data from Open-Meteo API as reliable free fallback
        cache_key = f"open_meteo_forecast:{latitude:.4f},{longitude:.4f}"
        cached = _cache_get(cache_key)
        if cached is not None:
            results.append(cached)
        else:
            resp = await _http_get_with_retry(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current_weather": True,
                    "daily": "precipitation_sum,rain_sum,precipitation_probability_max",
                    "forecast_days": 7,
                    "timezone": "auto",
                },
            )
            if resp is not None:
                data = resp.json()
                weather = data.get("current_weather", {})
                daily = data.get("daily", {})
                forecast_url = (
                    "https://api.open-meteo.com/v1/forecast?"
                    f"latitude={latitude}&longitude={longitude}&current_weather=true&"
                    "daily=precipitation_sum,rain_sum,precipitation_probability_max&"
                    "forecast_days=7&timezone=auto"
                )
                content_str = (
                    f"Live climate readings for {resolved_name}: Temperature is {weather.get('temperature')}°C, "
                    f"Wind Speed is {weather.get('windspeed')} km/h. "
                    f"Seven-day precipitation totals are {daily.get('precipitation_sum', [])} mm, "
                    f"with maximum daily precipitation probabilities of "
                    f"{daily.get('precipitation_probability_max', [])}%."
                )
                meteo_result = {
                    "source_name": "Open-Meteo Climate API",
                    "url": forecast_url,
                    "content": content_str,
                    "snippet": content_str,
                    "reliability_score": 0.90,
                    "topic": "weather_forecast",
                    "location": resolved_name,
                    "date": "live"
                }
                _cache_set(cache_key, meteo_result)
                results.append(meteo_result)
            else:
                logger.warning("Open-Meteo forecast API returned no response for %s", resolved_name)

        # 4. Add topic-specific public data products when the query needs them.
        if any(term in query.lower() for term in ("flood", "flooding", "river", "overflow")):
            flood_result = await self._query_open_meteo_flood(
                latitude, longitude, resolved_name
            )
            if flood_result:
                results.append(flood_result)

        if any(term in query.lower() for term in ("air quality", "pollution", "pm2.5", "smog")):
            air_quality_result = await self._query_open_meteo_air_quality(
                latitude, longitude, resolved_name
            )
            if air_quality_result:
                results.append(air_quality_result)

        if any(term in query.lower() for term in ("coastal", "coast", "wave", "sea level", "storm surge")):
            marine_result = await self._query_open_meteo_marine(
                latitude, longitude, resolved_name
            )
            if marine_result:
                results.append(marine_result)

        return results

    async def _query_open_meteo_flood(
        self, latitude: float, longitude: float, location: str
    ) -> dict | None:
        """Fetch seven-day river-discharge evidence from Open-Meteo Flood API."""
        endpoint = "https://flood-api.open-meteo.com/v1/flood"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "river_discharge",
            "forecast_days": 7,
        }
        cache_key = f"open_meteo_flood:{latitude:.4f},{longitude:.4f}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        resp = await _http_get_with_retry(endpoint, params)
        if resp is None:
            logger.warning("Open-Meteo Flood API returned no response for %s", location)
            return None

        data = resp.json()
        daily = data.get("daily", {})
        discharge = daily.get("river_discharge", [])
        if not discharge:
            return None

        query_params = httpx.QueryParams(params)
        result = {
            "source_name": "Open-Meteo Flood API",
            "url": f"{endpoint}?{query_params}",
            "content": (
                f"Seven-day river discharge forecast for {location}: "
                f"{discharge}. Higher discharge can increase river overflow risk; "
                "this is an indicator, not an official warning."
            ),
            "snippet": f"River discharge forecast for {location}: {discharge}.",
            "reliability_score": 0.90,
            "topic": "flood",
            "location": location,
            "date": "live",
        }
        _cache_set(cache_key, result)
        return result

    async def _query_open_meteo_air_quality(
        self, latitude: float, longitude: float, location: str
    ) -> dict | None:
        """Fetch current PM2.5 and AQI evidence from Open-Meteo Air Quality API."""
        endpoint = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "pm2_5,us_aqi",
            "timezone": "auto",
        }
        cache_key = f"open_meteo_air:{latitude:.4f},{longitude:.4f}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        resp = await _http_get_with_retry(endpoint, params)
        if resp is None:
            logger.warning("Open-Meteo Air Quality API returned no response for %s", location)
            return None

        data = resp.json().get("current", {})
        if not data:
            return None

        query_params = httpx.QueryParams(params)
        result = {
            "source_name": "Open-Meteo Air Quality API",
            "url": f"{endpoint}?{query_params}",
            "content": (
                f"Current air quality for {location}: PM2.5 is "
                f"{data.get('pm2_5')} micrograms per cubic meter and US AQI is "
                f"{data.get('us_aqi')}."
            ),
            "snippet": f"Current PM2.5 and US AQI for {location}.",
            "reliability_score": 0.90,
            "topic": "air-quality",
            "location": location,
            "date": "live",
        }
        _cache_set(cache_key, result)
        return result

    async def _query_open_meteo_marine(
        self, latitude: float, longitude: float, location: str
    ) -> dict | None:
        """Fetch seven-day wave and sea-level indicators from Open-Meteo Marine API."""
        endpoint = "https://marine-api.open-meteo.com/v1/marine"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "wave_height_max",
            "forecast_days": 7,
            "timezone": "auto",
        }
        cache_key = f"open_meteo_marine:{latitude:.4f},{longitude:.4f}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        resp = await _http_get_with_retry(endpoint, params)
        if resp is None:
            logger.warning("Open-Meteo Marine API returned no response for %s", location)
            return None

        daily = resp.json().get("daily", {})
        wave_heights = daily.get("wave_height_max", [])
        if not wave_heights:
            return None

        query_params = httpx.QueryParams(params)
        result = {
            "source_name": "Open-Meteo Marine API",
            "url": f"{endpoint}?{query_params}",
            "content": (
                f"Seven-day coastal indicators for {location}: maximum wave heights "
                f"{wave_heights} meters. Elevated wave heights can increase coastal hazard "
                "exposure; this is an indicator, not an official warning."
            ),
            "snippet": f"Wave and sea-level indicators for {location}.",
            "reliability_score": 0.90,
            "topic": "coastal-hazard",
            "location": location,
            "date": "live",
        }
        _cache_set(cache_key, result)
        return result


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = IRAgent()
    agent.run()
