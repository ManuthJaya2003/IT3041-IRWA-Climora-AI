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

import uuid
import httpx
from app.mcp.base_agent_server import BaseAgentServer
from app.config import settings

# Default coordinates used only if geocoding fails and no location was given at all.
DEFAULT_LOCATION_NAME = "Colombo, Sri Lanka"
DEFAULT_LATITUDE = 6.9271
DEFAULT_LONGITUDE = 79.8612


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
        """Initialize the embedding and vector store services this agent depends on."""
        from app.services.embedding_service import embedding_service
        from app.services.vector_store_service import vector_store_service

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

        # Build enhanced search query string from extracted NLP entities
        search_parts = [query]
        if entities.get("location"):
            search_parts.append(str(entities["location"]))
        if entities.get("climate_topic"):
            search_parts.append(str(entities["climate_topic"]))
        if entities.get("hazard_type"):
            search_parts.append(str(entities["hazard_type"]))

        search_query = " ".join([p for p in search_parts if p]).strip()

        # Step 1: Query FAISS Local Vector Store for semantically similar documents
        documents = []
        try:
            faiss_results = await vector_store_service.query_similar(
                query_text=search_query or "climate risk",
                top_k=top_k
            )

            for r in faiss_results:
                metadata = r.get("metadata", {})
                documents.append({
                    "source_name": metadata.get("source", "FAISS Local Store"),
                    "url": r.get("url", metadata.get("url", "")),
                    "content": r.get("content", ""),
                    "snippet": r.get("content", "")[:300],
                    "reliability_score": r.get("score", 0.85),
                    "topic": metadata.get("topic", "climate"),
                    "location": metadata.get("location", ""),
                    "date": metadata.get("date", "live")
                })
        except Exception:
            # Fallback gracefully if vector store is empty or unseeded
            pass

        # Step 2: Query External APIs (OpenWeatherMap & Open-Meteo) for live readings
        external_results = await self._search_external_sources(query, entities)
        documents.extend(external_results)

        # Step 3: Combine, rank, and limit results to top_k
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
        results = []

        # Resolve the location name to coordinates once, shared by both APIs below.
        latitude, longitude, resolved_name = await self._geocode_location(location)

        # OpenWeatherMap API Direct Call
        if "open_weather" in sources or "all" in sources:
            owm_result = await self._query_open_weather(location)
            if owm_result:
                results.append(owm_result)

        # Open-Meteo API Direct Call
        if "open_meteo" in sources or "all" in sources:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={"latitude": latitude, "longitude": longitude, "current_weather": True}
                    )
                    if resp.status_code == 200:
                        results.append({
                            "source_name": "Open-Meteo API",
                            "location": resolved_name,
                            "data": resp.json().get("current_weather", {}),
                            "status": "success"
                        })
            except Exception as e:
                results.append({"source_name": "Open-Meteo API", "error": str(e), "status": "failed"})

        return {"results": results}

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
        """
        if not location_name:
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_LOCATION_NAME

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": location_name, "count": 1},
                )
                if resp.status_code == 200:
                    results = resp.json().get("results") or []
                    if results:
                        place = results[0]
                        resolved_name = ", ".join(
                            filter(None, [place.get("name"), place.get("country")])
                        ) or location_name
                        return place["latitude"], place["longitude"], resolved_name
        except Exception:
            pass

        # Geocoding failed (network issue, unknown place name, etc.) - fall back
        # to the default coordinates rather than silently querying the wrong city.
        return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_LOCATION_NAME

    async def _query_open_weather(self, location: str) -> dict:
        """
        Helper method to fetch current weather details from OpenWeatherMap API.

        Uses settings.openweather_api_key configured in .env file.
        """
        api_key = settings.openweather_api_key
        if not api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"q": location, "appid": api_key, "units": "metric"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    weather_desc = data["weather"][0]["description"]
                    temp = data["main"]["temp"]
                    humidity = data["main"]["humidity"]
                    wind_speed = data["wind"]["speed"]

                    content_str = (
                        f"Current weather in {location}: {weather_desc}, Temperature: {temp}°C, "
                        f"Humidity: {humidity}%, Wind Speed: {wind_speed} m/s."
                    )
                    return {
                        "source_name": "OpenWeatherMap API",
                        "url": f"https://openweathermap.org/city/{data.get('id', '')}",
                        "content": content_str,
                        "snippet": content_str,
                        "reliability_score": 0.95,
                        "topic": "current_weather",
                        "location": location,
                        "date": "live"
                    }
        except Exception:
            pass
        return None

    async def _search_external_sources(self, query: str, entities: dict) -> list:
        """
        Helper method to query all external climate and weather APIs (OpenWeatherMap & Open-Meteo).
        """
        results = []
        location = entities.get("location", "")
        if isinstance(location, list) and location:
            location = location[0]
        loc_str = str(location) if location else DEFAULT_LOCATION_NAME

        # 1. Fetch live data from OpenWeatherMap API
        owm_data = await self._query_open_weather(loc_str)
        if owm_data:
            results.append(owm_data)

        # 2. Resolve loc_str to real coordinates before calling Open-Meteo, so the
        #    forecast actually matches the requested location instead of always
        #    returning Colombo's weather.
        latitude, longitude, resolved_name = await self._geocode_location(loc_str)

        # 3. Fetch live data from Open-Meteo API as reliable free fallback
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={"latitude": latitude, "longitude": longitude, "current_weather": True}
                )
                if resp.status_code == 200:
                    weather = resp.json().get("current_weather", {})
                    content_str = (
                        f"Live climate readings for {resolved_name}: Temperature is {weather.get('temperature')}°C, "
                        f"Wind Speed is {weather.get('windspeed')} km/h."
                    )
                    results.append({
                        "source_name": "Open-Meteo Climate API",
                        "url": "https://open-meteo.com",
                        "content": content_str,
                        "snippet": content_str,
                        "reliability_score": 0.90,
                        "topic": "weather_forecast",
                        "location": resolved_name,
                        "date": "live"
                    })
        except Exception:
            pass

        return results


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = IRAgent()
    agent.run()