"""
Orchestrator / Supervisor Agent

The central coordinator of the Climora AI multi-agent system.
Responsibilities:
- Receives user requests from the API layer
- Determines the processing workflow based on query type
- Dispatches tasks to specialized agents via MCP
- Collects and combines results from agents
- Assembles the final response with evidence and recommendations
- Controls the overall flow and handles errors/fallbacks

Communication: Uses MCP (Model Context Protocol) to invoke tools exposed
by each specialized agent running as an MCP server.
"""

import asyncio
import uuid
import time
from typing import Optional
from datetime import datetime, timezone

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    RiskAssessment,
    Recommendation,
    SourceEvidence,
    AgentTaskMessage,
    AgentTaskResult,
    RiskLevel,
)
from app.agents.orchestrator.mcp_client import MCPClientManager
from app.services.llm_service import llm_service


class OrchestratorAgent:
    """
    The Orchestrator Agent coordinates all specialized agents to process
    user climate queries through the multi-agent pipeline.

    Pipeline flow:
    1. Security Agent → validates input
    2. NLP Agent → extracts intent, entities, structures query
    3. IR Agent → retrieves relevant climate evidence
    4. Analysis Agent → analyzes evidence, assesses risk
    5. Verification Agent → validates claims and sources
    6. Recommendation Agent → generates actionable recommendations
    7. Orchestrator → assembles final response
    """

    def __init__(self):
        self.agent_name = "orchestrator"
        self.mcp_client = MCPClientManager()
        self._session_store: dict[str, list] = {}  # Simple in-memory session storage

    async def process_user_query(self, request: ChatRequest) -> ChatResponse:
        """
        Main entry point: process a user's climate query through the full agent pipeline.

        Args:
            request: The user's chat request with query, location, etc.

        Returns:
            ChatResponse with summary, analysis, recommendations, and sources.
        """
        start_time = time.time()
        session_id = request.session_id or str(uuid.uuid4())
        agents_used = []

        try:
            # --- Step 0: Language Detection ---
            from app.services.language_service import detect_language, get_language_name
            detected_language = detect_language(request.query)

            # --- Steps 1 & 2: Security + NLP in parallel ---
            # These two are independent — neither depends on the other's output.
            security_task = asyncio.create_task(self._invoke_security_agent(request))
            nlp_task = asyncio.create_task(self._invoke_nlp_agent(request))
            security_result, nlp_result = await asyncio.gather(security_task, nlp_task)
            agents_used.extend(["security_agent", "nlp_agent"])

            if not security_result.get("safe", True):
                return self._build_blocked_response(
                    session_id, request.query, security_result.get("reason", "Request blocked")
                )

            structured_query = nlp_result.get("structured_query", {})
            intent = nlp_result.get("intent", "general_climate_query")
            entities = nlp_result.get("entities", {})

            # Forward the NLP agent's expanded_query into structured_query so the
            # IR agent can use it for better FAISS semantic search.
            expanded_query = nlp_result.get("expanded_query", "")
            if expanded_query:
                structured_query["expanded_query"] = expanded_query

            # --- Step 2a: Context-aware follow-up handling ---
            # If the user replied with just a location name (e.g. "kandy") after
            # being asked to specify a location, reconstruct their intent from the
            # previous session message and synthesise a full query.
            from app.agents.ir_agent.ir_agent import LOCATION_ALIASES
            query_stripped = request.query.strip().lower()
            is_location_only = (
                len(query_stripped.split()) <= 3
                and not entities.get("climate_topic")
                and not entities.get("hazard_type")
                and any(kw in query_stripped for kw in list(LOCATION_ALIASES.keys()) + ["sri lanka"])
            )
            if is_location_only and request.session_id:
                history = self._session_store.get(request.session_id, [])
                if history:
                    last_summary = history[-1].get("response_summary", "").lower()
                    asked_for_location = "please specify a location" in last_summary or "specify a location" in last_summary
                    if asked_for_location:
                        # Reconstruct: use previous intent if available, default to weather
                        last_query = history[-1].get("query", "").lower()
                        if any(w in last_query for w in ["flood", "flooding"]):
                            synthesised = f"flood risk in {request.query.strip()}"
                        elif any(w in last_query for w in ["drought"]):
                            synthesised = f"drought in {request.query.strip()}"
                        elif any(w in last_query for w in ["rain", "rainfall"]):
                            synthesised = f"rainfall in {request.query.strip()}"
                        elif any(w in last_query for w in ["cyclone", "storm"]):
                            synthesised = f"cyclone risk in {request.query.strip()}"
                        else:
                            synthesised = f"weather in {request.query.strip()}"
                        # Re-run NLP on the synthesised query
                        from app.models.schemas import ChatRequest as CR
                        synthetic_request = CR(
                            query=synthesised,
                            location=request.location,
                            user_type=request.user_type,
                            session_id=request.session_id,
                            context=request.context,
                        )
                        nlp_result = await self._invoke_nlp_agent(synthetic_request)
                        structured_query = nlp_result.get("structured_query", {})
                        intent = nlp_result.get("intent", "general_climate_query")
                        entities = nlp_result.get("entities", {})
                        expanded_query = nlp_result.get("expanded_query", "")
                        if expanded_query:
                            structured_query["expanded_query"] = expanded_query

            # --- Step 2b: Sri Lanka geo-restriction (runs BEFORE non-climate check) ---
            # If the user mentions a foreign country/city, tell them the system
            # only covers Sri Lanka — regardless of whether a climate term is present.
            FOREIGN_INDICATORS_EARLY = [
                "india", "indian", "pakistan", "bangladesh", "nepal", "bhutan",
                "myanmar", "burma", "afghanistan",
                "thailand", "singapore", "malaysia", "indonesia", "philippines",
                "vietnam", "cambodia", "laos", "brunei",
                "china", "japan", "korea", "taiwan", "hong kong", "mongolia",
                "dubai", "uae", "saudi", "arabia", "qatar", "kuwait", "oman",
                "bahrain", "iraq", "iran", "turkey", "israel", "jordan",
                "uk", "united kingdom", "england", "scotland", "wales", "ireland",
                "france", "germany", "italy", "spain", "portugal", "netherlands",
                "belgium", "switzerland", "austria", "sweden", "norway", "denmark",
                "finland", "poland", "greece", "russia",
                "usa", "united states", "america", "canada", "mexico", "brazil",
                "argentina", "colombia", "chile", "peru",
                "australia", "new zealand",
                "south africa", "nigeria", "kenya", "egypt",
                "new york", "london", "paris", "berlin", "tokyo", "beijing",
                "shanghai", "sydney", "toronto", "moscow", "rome", "madrid",
                "mumbai", "delhi", "chennai", "kolkata", "bangalore", "hyderabad",
                "karachi", "dhaka", "kathmandu", "islamabad", "bangkok",
                "kuala lumpur", "jakarta", "manila", "hong kong", "seoul", "cairo",
            ]
            import re as _re
            _query_lower_early = request.query.lower()
            _detected_location_early = entities.get("location", "") or ""
            _is_foreign_early = any(
                _re.search(r'\b' + _re.escape(fi) + r'\b', _query_lower_early)
                for fi in FOREIGN_INDICATORS_EARLY
            )
            if not _is_foreign_early and _detected_location_early:
                _is_foreign_early = any(
                    fi in _detected_location_early.lower() for fi in FOREIGN_INDICATORS_EARLY
                )
            if _is_foreign_early:
                _foreign_place = _detected_location_early or next(
                    (fi for fi in FOREIGN_INDICATORS_EARLY if fi in _query_lower_early), "that location"
                )
                return ChatResponse(
                    session_id=session_id,
                    query=request.query,
                    summary=(
                        f"Climora AI currently covers Sri Lanka only. "
                        f"Climate data for '{_foreign_place}' is not available in this system. "
                        "Please ask about a location within Sri Lanka — for example: "
                        "'What is the weather in Colombo?' or 'What is the flood risk in Kandy?'"
                    ),
                    confidence_score=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    agents_used=agents_used,
                )

            # --- Step 2c: Reject non-climate queries at orchestrator level ---
            if not entities.get("climate_topic") and not entities.get("hazard_type"):
                from app.agents.ir_agent.ir_agent import CLIMATE_QUERY_TERMS
                query_lower = request.query.lower()
                import re
                has_climate_term = any(
                    re.search(r'\b' + re.escape(term) + r'\b', query_lower)
                    for term in CLIMATE_QUERY_TERMS
                )
                if not has_climate_term or intent == "non_climate":
                    return ChatResponse(
                        session_id=session_id,
                        query=request.query,
                        summary="I can only answer climate and environmental questions for locations in Sri Lanka. Please ask about weather, hazards, climate risks, flood, drought, or preparedness for a Sri Lankan location.",
                        confidence_score=0.0,
                        processing_time_ms=(time.time() - start_time) * 1000,
                        agents_used=agents_used,
                    )

            # --- Step 2d: Sri Lanka location clarification ---
            #
            # Logic:
            #   1. Query mentions a Sri Lanka location  → proceed normally
            #   2. Query has no location at all         → ask user to specify
            #      (climate queries need a location to retrieve meaningful data)
            # Note: Foreign location check is already done in Step 2b above.
            detected_location = entities.get("location", "") or ""
            query_lower_geo = request.query.lower()

            from app.agents.ir_agent.ir_agent import LOCATION_ALIASES

            # Check if the query text contains a known Sri Lanka location
            has_sri_lanka_location = bool(detected_location) or any(
                kw in query_lower_geo
                for kw in list(LOCATION_ALIASES.keys()) + ["sri lanka", "ceylon"]
            )

            if not has_sri_lanka_location:
                # Climate query with no location — ask the user to specify.
                # Store the session entry so the next message (a location reply)
                # can look back and reconstruct the intent.
                ask_response = ChatResponse(
                    session_id=session_id,
                    query=request.query,
                    summary="Please specify a location in Sri Lanka for your query. For example: 'What is the weather in Colombo?', 'Is there a flood risk in Kandy?', or 'What is the drought situation in Jaffna?'",
                    confidence_score=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    agents_used=agents_used,
                )
                self._store_session(session_id, request.query, ask_response)
                return ask_response

            # --- Step 3: Information Retrieval ---
            ir_result = await self._invoke_ir_agent(structured_query, entities)
            agents_used.append("ir_agent")

            retrieved_evidence = ir_result.get("documents", [])

            if not retrieved_evidence:
                verification_result = await self._invoke_verification_agent(
                    claims=[],
                    sources=[],
                )
                agents_used.append("verification_agent")
                return ChatResponse(
                    session_id=session_id,
                    query=request.query,
                    summary="I can only answer climate and environmental questions. Please ask about weather, hazards, climate risks, or preparedness.",
                    verification_results=verification_result,
                    confidence_score=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    agents_used=agents_used,
                )

            # --- Step 4: Climate Analysis ---
            analysis_result = await self._invoke_analysis_agent(
                query=request.query,
                intent=intent,
                entities=entities,
                evidence=retrieved_evidence,
            )
            agents_used.append("analysis_agent")

            # --- Steps 5 & 6: Verification + Recommendations in parallel ---
            # Both depend only on analysis_result and retrieved_evidence — they
            # don't need each other, so run them concurrently.
            verification_task = asyncio.create_task(
                self._invoke_verification_agent(
                    claims=analysis_result.get("claims", []),
                    sources=retrieved_evidence,
                )
            )
            recommendation_task = asyncio.create_task(
                self._invoke_recommendation_agent(
                    analysis=analysis_result,
                    user_type=request.user_type,
                    location=request.location,
                )
            )
            verification_result, recommendation_result = await asyncio.gather(
                verification_task, recommendation_task
            )
            agents_used.extend(["verification_agent", "recommendation_agent"])

            # --- Step 7: Assemble Final Response ---
            response = await self._assemble_response(
                session_id=session_id,
                request=request,
                nlp_result=nlp_result,
                ir_result=ir_result,
                analysis_result=analysis_result,
                verification_result=verification_result,
                recommendation_result=recommendation_result,
                agents_used=agents_used,
                start_time=start_time,
                language=detected_language,
            )

            # Store in session
            self._store_session(session_id, request.query, response)

            return response

        except Exception as e:
            # Graceful error handling
            processing_time = (time.time() - start_time) * 1000
            return ChatResponse(
                session_id=session_id,
                query=request.query,
                summary=f"I encountered an issue while processing your climate query. Please try again.",
                detailed_analysis=f"Error details: {str(e)}",
                agents_used=agents_used,
                processing_time_ms=processing_time,
            )

    # =========================================================================
    # Agent Invocation Methods (via MCP)
    # =========================================================================

    async def _invoke_security_agent(self, request: ChatRequest) -> dict:
        """Invoke the Security Agent to validate the input."""
        task = AgentTaskMessage(
            task_id=str(uuid.uuid4()),
            source_agent=self.agent_name,
            target_agent="security_agent",
            task_type="validate_input",
            payload={
                "query": request.query,
                "location": request.location,
                "context": request.context,
            },
        )

        result = await self.mcp_client.call_agent_tool(
            agent_name="security_agent",
            tool_name="validate_input",
            arguments=task.payload,
        )

        if result and "error" not in result:
            return result
        return {"safe": True, "reason": "Security agent unavailable - allowing request"}

    async def _invoke_nlp_agent(self, request: ChatRequest) -> dict:
        """Invoke the NLP Agent for intent detection and entity extraction."""
        task_payload = {
            "query": request.query,
            "location": request.location,
            "user_type": request.user_type.value if request.user_type else None,
            "context": request.context,
        }

        result = await self.mcp_client.call_agent_tool(
            agent_name="nlp_agent",
            tool_name="process_query",
            arguments=task_payload,
        )

        if result and "error" not in result:
            return result

        # Fallback: use LLM directly for basic NLP if agent is unavailable
        return await self._fallback_nlp(request)

    async def _invoke_ir_agent(self, structured_query: dict, entities: dict) -> dict:
        """Invoke the Information Retrieval Agent to find relevant evidence."""
        task_payload = {
            "structured_query": structured_query,
            "entities": entities,
            "top_k": 5,
        }

        result = await self.mcp_client.call_agent_tool(
            agent_name="ir_agent",
            tool_name="retrieve_documents",
            arguments=task_payload,
        )

        if result and "error" not in result:
            return result

        # Fallback: query FAISS directly when IR agent isn't running
        return await self._fallback_ir(structured_query, entities)

    async def _invoke_analysis_agent(
        self, query: str, intent: str, entities: dict, evidence: list
    ) -> dict:
        """Invoke the Climate Analysis Agent to assess risk and patterns."""
        task_payload = {
            "query": query,
            "intent": intent,
            "entities": entities,
            "evidence": evidence,
        }

        result = await self.mcp_client.call_agent_tool(
            agent_name="analysis_agent",
            tool_name="analyze_climate_data",
            arguments=task_payload,
        )

        if result and "error" not in result:
            return result

        # Fallback: use LLM directly
        return await self._fallback_analysis(query, evidence)

    async def _invoke_verification_agent(self, claims: list, sources: list) -> dict:
        """Invoke the Verification Agent to check source quality and claims."""
        task_payload = {
            "claims": claims,
            "sources": sources,
        }

        result = await self.mcp_client.call_agent_tool(
            agent_name="verification_agent",
            tool_name="verify_claims",
            arguments=task_payload,
        )

        if result and "error" not in result:
            return result

        return {"verified": True, "confidence": 0.5, "message": "Verification agent unavailable"}

    async def _invoke_recommendation_agent(
        self, analysis: dict, user_type: Optional[str], location: Optional[str]
    ) -> dict:
        """Invoke the Recommendation Agent to generate actionable guidance."""
        task_payload = {
            "analysis": analysis,
            "user_type": user_type.value if user_type else "individual",
            "location": location,
        }

        result = await self.mcp_client.call_agent_tool(
            agent_name="recommendation_agent",
            tool_name="generate_recommendations",
            arguments=task_payload,
        )

        if result and "error" not in result:
            return result

        # Fallback: generate recommendations using LLM
        return await self._fallback_recommendations(analysis, user_type, location)

    # =========================================================================
    # Response Assembly
    # =========================================================================

    async def _assemble_response(
        self,
        session_id: str,
        request: ChatRequest,
        nlp_result: dict,
        ir_result: dict,
        analysis_result: dict,
        verification_result: dict,
        recommendation_result: dict,
        agents_used: list[str],
        start_time: float,
        language: str = "en",
    ) -> ChatResponse:
        """Assemble the final response from all agent outputs."""

        processing_time = (time.time() - start_time) * 1000

        # Build summary using LLM to synthesize all agent outputs
        summary = await self._generate_summary(
            query=request.query,
            analysis=analysis_result,
            verification=verification_result,
            language=language,
        )

        # Build risk assessment
        risk_assessment = None
        if analysis_result.get("risk_level"):
            risk_assessment = RiskAssessment(
                risk_level=analysis_result.get("risk_level", RiskLevel.UNKNOWN),
                risk_factors=analysis_result.get("risk_factors", []),
                confidence=verification_result.get("confidence", 0.5),
                explanation=analysis_result.get("risk_explanation", ""),
            )

        # Build recommendations list
        recommendations = [
            Recommendation(
                action=rec.get("action", ""),
                priority=rec.get("priority", "short-term"),
                explanation=rec.get("explanation", ""),
            )
            for rec in recommendation_result.get("recommendations", [])
        ]

        # Build sources list.
        # FAISS cosine similarity scores (0.15-0.30) are raw similarity values,
        # not reliability ratings. Cap them at a minimum of 0.60 so FAISS-sourced
        # documents don't appear as "15% reliable" in the UI — their actual
        # content quality is validated by the seeding process.
        sources = [
            SourceEvidence(
                source_name=doc.get("source_name", "Unknown Source"),
                source_url=doc.get("url"),
                content_snippet=doc.get("snippet", doc.get("content", "")[:200]),
                reliability_score=max(0.60, float(doc.get("reliability_score") or 0.60)),
            )
            for doc in ir_result.get("documents", [])
        ]

        # Overall confidence
        confidence = verification_result.get("confidence", 0.5)

        return ChatResponse(
            session_id=session_id,
            query=request.query,
            summary=summary,
            detailed_analysis=analysis_result.get("detailed_analysis"),
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            sources=sources,
            retrieved_sources=ir_result.get("documents", []),
            extracted_facts=analysis_result.get("claims", []),
            verification_results=verification_result,
            confidence_score=confidence,
            processing_time_ms=processing_time,
            agents_used=agents_used,
            language=language,
        )

    async def _generate_summary(
        self, query: str, analysis: dict, verification: dict, language: str = "en"
    ) -> str:
        """Use the LLM to generate a user-friendly summary from agent outputs."""
        from app.services.language_service import get_response_instruction

        language_instruction = get_response_instruction(language)

        prompt = f"""Based on the following climate analysis, provide a clear and concise summary 
for the user who asked: "{query}"

Analysis findings: {analysis.get('summary', 'No analysis available')}
Risk level: {analysis.get('risk_level', 'unknown')}
Risk factors: {', '.join(analysis.get('risk_factors', [])) or 'None identified'}
Verification status: {'Verified' if verification.get('verified') else 'Partially verified'}
Confidence: {verification.get('confidence', 'Unknown')}

Provide a helpful, evidence-based summary in 2-4 sentences. Be specific about the risks 
and what the user should know. Be clear about what is known and what is uncertain. 
Do not make claims beyond what the evidence supports.

{language_instruction}"""

        system_prompt = (
            "You are Climora AI, a climate intelligence assistant. "
            "Provide clear, evidence-based responses. "
            "Always communicate uncertainty honestly. "
            "Never present uncertain information as fact. "
            f"{language_instruction}"
        )

        response = await llm_service.invoke_model(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.4,
        )

        return response

    # =========================================================================
    # Fallback Methods (when agents are unavailable)
    # =========================================================================

    async def _fallback_nlp(self, request: ChatRequest) -> dict:
        """
        Fallback NLP processing — rule-based extraction without an LLM call.

        Key improvement: extracts location directly from query text so users
        don't have to fill the separate location field. Covers all 25 Sri Lanka
        districts, 9 provinces, and common geographic sub-regions.
        """
        query = request.query.lower()

        # ------------------------------------------------------------------
        # Hard blocklist — reject clearly non-climate questions even if they
        # mention a Sri Lanka place name (e.g. "Kandy train timetable").
        # These terms have no climate meaning and should never produce results.
        # ------------------------------------------------------------------
        NON_CLIMATE_TERMS = [
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
        if any(term in query for term in NON_CLIMATE_TERMS):
            # Return empty entities with no climate topic — orchestrator will reject
            return {
                "intent": "non_climate",
                "entities": {},
                "structured_query": {"original_query": request.query},
                "expanded_terms": [],
            }

        # ------------------------------------------------------------------
        # Location extraction — query text takes priority over the location
        # field, because users type "flood risk in Kandy" without filling the
        # separate location box. The location field is used as fallback only.
        # ------------------------------------------------------------------

        # All 25 Sri Lanka districts + provinces + common sub-regions,
        # ordered longest-first so "nuwara eliya" matches before "eliya".
        SRI_LANKA_LOCATIONS = [
            # Districts (longest/most specific first)
            ("nuwara eliya",     "Nuwara Eliya, Sri Lanka"),
            ("anuradhapura",     "Anuradhapura, Sri Lanka"),
            ("polonnaruwa",      "Polonnaruwa, Sri Lanka"),
            ("trincomalee",      "Trincomalee, Sri Lanka"),
            ("hambantota",       "Hambantota, Sri Lanka"),
            ("kilinochchi",      "Kilinochchi, Sri Lanka"),
            ("mullaitivu",       "Mullaitivu, Sri Lanka"),
            ("vavuniya",         "Vavuniya, Sri Lanka"),
            ("batticaloa",       "Batticaloa, Sri Lanka"),
            ("monaragala",       "Monaragala, Sri Lanka"),
            ("kurunegala",       "Kurunegala, Sri Lanka"),
            ("ratnapura",        "Ratnapura, Sri Lanka"),
            ("kalpitiya",        "Kalpitiya, Sri Lanka"),
            ("kalutara",         "Kalutara, Sri Lanka"),
            ("gampaha",          "Gampaha, Sri Lanka"),
            ("matale",           "Matale, Sri Lanka"),
            ("badulla",          "Badulla, Sri Lanka"),
            ("kegalle",          "Kegalle, Sri Lanka"),
            ("ampara",           "Ampara, Sri Lanka"),
            ("puttalam",         "Puttalam, Sri Lanka"),
            ("matara",           "Matara, Sri Lanka"),
            ("mannar",           "Mannar, Sri Lanka"),
            ("kandy",            "Kandy, Sri Lanka"),
            ("galle",            "Galle, Sri Lanka"),
            ("jaffna",           "Jaffna, Sri Lanka"),
            ("colombo",          "Colombo, Sri Lanka"),
            # Provinces
            ("western province",      "Western Province, Sri Lanka"),
            ("central province",      "Central Province, Sri Lanka"),
            ("southern province",     "Southern Province, Sri Lanka"),
            ("northern province",     "Northern Province, Sri Lanka"),
            ("eastern province",      "Eastern Province, Sri Lanka"),
            ("north western province","North Western Province, Sri Lanka"),
            ("north central province","North Central Province, Sri Lanka"),
            ("uva province",          "Uva Province, Sri Lanka"),
            ("sabaragamuwa",          "Sabaragamuwa Province, Sri Lanka"),
            # Sub-regions / geographic features
            ("dry zone",         "Dry Zone, Sri Lanka"),
            ("hill country",     "Central Highlands, Sri Lanka"),
            ("knuckles",         "Matale, Sri Lanka"),
            ("horton plains",    "Nuwara Eliya, Sri Lanka"),
            ("wilpattu",         "Anuradhapura, Sri Lanka"),
            ("yala",             "Hambantota, Sri Lanka"),
            ("sinharaja",        "Sinharaja, Sri Lanka"),
            ("mahaweli",         "Mahaweli Basin, Sri Lanka"),
            ("kelani",           "Colombo, Sri Lanka"),
            ("sri lanka",        "Sri Lanka"),
        ]

        # Extract location from query — use first match found
        detected_location = None
        for keyword, canonical in SRI_LANKA_LOCATIONS:
            if keyword in query:
                detected_location = canonical
                break

        # Fall back to the separate location field if query has no location
        location = detected_location or request.location or None

        # ------------------------------------------------------------------
        # Intent detection
        # ------------------------------------------------------------------
        intent = "general_climate_query"
        if any(w in query for w in ["risk", "danger", "threat", "vulnerable", "hazard"]):
            intent = "risk_awareness"
        elif any(w in query for w in ["prepare", "should i", "what to do", "how to", "advice"]):
            intent = "preparedness"
        elif any(w in query for w in ["forecast", "predict", "next week", "tomorrow", "upcoming"]):
            intent = "forecast"
        elif any(w in query for w in ["history", "trend", "past", "change over", "last year"]):
            intent = "trend_analysis"

        # ------------------------------------------------------------------
        # Climate topic detection — expanded keyword lists
        # ------------------------------------------------------------------
        topic_keywords = {
            "flood":        ["flood", "flooding", "inundation", "overflow", "waterlog", "flash flood", "river level", "discharge"],
            "drought":      ["drought", "dry spell", "water scarcity", "arid", "low rainfall", "water shortage"],
            "heat-wave":    ["heat wave", "heatwave", "heat stress", "heat island", "extreme heat", "heat index"],
            "cyclone":      ["cyclone", "hurricane", "typhoon", "tropical storm", "storm surge", "wind speed"],
            "landslide":    ["landslide", "mudslide", "slope failure", "debris flow", "hillside collapse"],
            "sea-level-rise":["sea level", "coastal erosion", "storm surge", "shoreline erosion", "tidal flooding"],
            "rain":         ["rainfall", "monsoon", "precipitation", "downpour", "heavy rain"],
            "air-quality":  ["air quality", "pollution", "pm2.5", "smog", "particulate", "aqi"],
            "wildfire":     ["wildfire", "forest fire", "fire risk", "bush fire", "burning forest"],
            "erosion":      ["erosion", "soil erosion", "bank erosion", "sediment", "topsoil loss"],
            "water-scarcity":["groundwater", "aquifer", "water table", "drinking water shortage", "water stress"],
            "agriculture":  ["crop failure", "crop damage", "harvest loss", "farming climate", "climate agriculture",
                             "drought crop", "flood crop", "monsoon farming", "yield decline"],
        }

        climate_topic = None
        hazard_type = None
        for topic, keywords in topic_keywords.items():
            if any(kw in query for kw in keywords):
                climate_topic = topic
                hazard_type = topic
                break

        entities: dict = {}
        if location:
            entities["location"] = location
        if climate_topic:
            entities["climate_topic"] = climate_topic
            entities["hazard_type"] = hazard_type

        return {
            "intent": intent,
            "entities": entities,
            "structured_query": {"original_query": request.query},
            "expanded_terms": [],
        }

    async def _fallback_ir(self, structured_query: dict, entities: dict) -> dict:
        """
        Fallback IR: query FAISS vector store directly when IR agent isn't running.
        Applies the same location filter as the IR agent so Kandy queries don't
        return Colombo or Galle documents.
        """
        from app.services.vector_store_service import vector_store_service
        from app.agents.ir_agent.ir_agent import _location_matches, CLIMATE_QUERY_TERMS

        if not vector_store_service.is_available() or vector_store_service._index.ntotal == 0:
            return {"documents": [], "message": "No documents in vector store"}

        original_query = structured_query.get("original_query", "")

        # Reject non-climate queries early
        query_lower = original_query.lower()
        has_climate_entities = entities.get("climate_topic") or entities.get("hazard_type")
        if not has_climate_entities and not any(t in query_lower for t in CLIMATE_QUERY_TERMS):
            return {"documents": [], "message": "No climate-related evidence was retrieved for this query."}

        # Build search query — include location for better embedding match
        location = entities.get("location", "")
        if isinstance(location, list):
            location = location[0] if location else ""
        search_query = original_query
        if location and location.lower() not in search_query.lower():
            search_query = f"{search_query} {location}"

        # Over-fetch to compensate for post-filter location filtering
        results = await vector_store_service.query_similar(
            query_text=search_query,
            top_k=15,
        )

        # Format and apply location filter
        documents = []
        seen_content: set[str] = set()
        for result in results:
            metadata = result.get("metadata", {})
            doc = {
                "source_name": result.get("source_name", metadata.get("source", "Unknown")),
                "url": result.get("url"),
                "content": result.get("content", ""),
                "snippet": result.get("snippet", result.get("content", "")[:300]),
                "reliability_score": min(result.get("score", 0.5), 1.0),
                "topic": metadata.get("topic", ""),
                "location": metadata.get("location", ""),
                "date": metadata.get("date", ""),
            }
            # Skip test documents
            if doc["source_name"].strip().lower() == "test":
                continue
            # Apply fuzzy location filter — same logic as IR agent
            if location and doc["location"]:
                if not _location_matches(location, str(doc["location"])):
                    continue
            # Deduplicate by content
            content_key = doc["content"][:120].strip()
            if content_key in seen_content:
                continue
            seen_content.add(content_key)
            documents.append(doc)
            if len(documents) >= 5:
                break

        return {
            "documents": documents,
            "source": "faiss_fallback",
            "query_used": search_query,
        }

    async def _fallback_analysis(self, query: str, evidence: list) -> dict:
        """Fallback analysis using LLM directly with retrieved evidence."""
        # Format evidence for the LLM
        evidence_text = ""
        if evidence:
            for i, doc in enumerate(evidence[:5], 1):
                source = doc.get("source_name", "Unknown")
                content = doc.get("content", doc.get("snippet", ""))[:500]
                location = doc.get("location", "")
                date = doc.get("date", "")
                evidence_text += f"\n[Source {i}: {source}]"
                if location:
                    evidence_text += f" (Location: {location})"
                if date:
                    evidence_text += f" (Date: {date})"
                evidence_text += f"\n{content}\n"
        else:
            evidence_text = "No evidence available."

        prompt = f"""You are a climate analysis agent. Analyze the following query using the retrieved evidence.

USER QUERY: "{query}"

RETRIEVED EVIDENCE:
{evidence_text}

Based ONLY on the evidence above, provide your analysis as a JSON object with these exact keys:
- "summary": 2-3 sentence summary of findings
- "risk_level": one of "low", "moderate", "high", "critical" (based on evidence severity)
- "risk_factors": list of specific risk factors found in evidence
- "risk_explanation": why you assigned this risk level
- "detailed_analysis": a detailed paragraph analyzing the situation
- "claims": list of key factual claims from your analysis

IMPORTANT: You MUST assign a risk level based on the evidence — do not say "unknown" if evidence exists.
Return ONLY the JSON object, no other text."""

        response = await llm_service.invoke_model(
            prompt=prompt,
            system_prompt="Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the JSON.",
            max_tokens=1000,
            temperature=0.2,
        )

        # Robust JSON parsing — handle markdown fences, extra text, etc.
        import json
        import re

        parsed = self._parse_json_response(response)
        if parsed:
            return parsed

        # If all parsing fails but we have evidence, provide a basic analysis
        if evidence:
            top_doc = evidence[0]
            return {
                "summary": f"Based on available evidence from {top_doc.get('source_name', 'retrieved sources')}, this area faces climate-related risks that warrant attention.",
                "risk_level": "moderate",
                "risk_factors": [top_doc.get("topic", "climate risk")],
                "risk_explanation": "Evidence suggests elevated risk based on retrieved climate data.",
                "detailed_analysis": top_doc.get("content", ""),
                "claims": [f"Information from {top_doc.get('source_name', 'source')} indicates relevant climate concerns."],
            }

        return {
            "summary": "Insufficient data for analysis.",
            "risk_level": "unknown",
            "risk_factors": [],
            "detailed_analysis": None,
            "claims": [],
        }

    def _parse_json_response(self, response: str) -> dict | None:
        """
        Robustly parse JSON from LLM response.
        Handles markdown fences, extra text before/after JSON, etc.
        """
        import json
        import re

        if not response:
            return None

        # Try direct parse first
        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            pass

        # Strip markdown code fences
        cleaned = re.sub(r'```json\s*', '', response)
        cleaned = re.sub(r'```\s*', '', cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find JSON object in the response
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    async def _fallback_recommendations(
        self, analysis: dict, user_type: Optional[str], location: Optional[str]
    ) -> dict:
        """Generate recommendations using LLM based on analysis results."""
        risk_level = analysis.get("risk_level", "unknown")
        risk_factors = analysis.get("risk_factors", [])
        summary = analysis.get("summary", "")

        prompt = f"""Based on the following climate analysis, generate 3 practical recommendations.

Analysis Summary: {summary}
Risk Level: {risk_level}
Risk Factors: {', '.join(risk_factors) if risk_factors else 'None identified'}
User Type: {user_type or 'individual'}
Location: {location or 'Not specified'}

Generate exactly 3 recommendations as a JSON object with key "recommendations" containing a list.
Each recommendation must have:
- "action": specific, practical action the user should take
- "priority": one of "immediate", "short-term", "long-term"
- "explanation": brief reason why this is important

Tailor recommendations to the user type and risk level. Be specific and actionable.
Return ONLY the JSON object."""

        response = await llm_service.invoke_model(
            prompt=prompt,
            system_prompt="Return ONLY a valid JSON object. No markdown, no explanation. Just JSON.",
            max_tokens=600,
            temperature=0.3,
        )

        parsed = self._parse_json_response(response)
        if parsed and "recommendations" in parsed:
            return parsed

        # If parsing fails, provide basic recommendations based on risk level
        if risk_level in ("high", "critical"):
            return {
                "recommendations": [
                    {"action": "Monitor official weather and disaster alerts for your area", "priority": "immediate", "explanation": f"Risk level is {risk_level} — stay alert."},
                    {"action": "Prepare an emergency kit with essentials (water, documents, first aid)", "priority": "short-term", "explanation": "Be ready to act if conditions worsen."},
                    {"action": "Review evacuation routes and emergency contacts", "priority": "short-term", "explanation": "Preparedness reduces risk during climate events."},
                ]
            }
        else:
            return {
                "recommendations": [
                    {"action": "Stay informed about local climate conditions and forecasts", "priority": "short-term", "explanation": "Awareness is the first step in preparedness."},
                    {"action": "Review your property and household preparedness for climate events", "priority": "long-term", "explanation": "Proactive measures reduce vulnerability."},
                    {"action": "Connect with local disaster management resources", "priority": "long-term", "explanation": "Know who to contact and where to get information."},
                ]
            }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _build_blocked_response(
        self, session_id: str, query: str, reason: str
    ) -> ChatResponse:
        """Build a response for blocked/unsafe requests."""
        return ChatResponse(
            session_id=session_id,
            query=query,
            summary=f"Your request could not be processed: {reason}",
            agents_used=["security_agent"],
        )

    def _store_session(self, session_id: str, query: str, response: ChatResponse):
        """Store query/response in session history."""
        if session_id not in self._session_store:
            self._session_store[session_id] = []
        self._session_store[session_id].append({
            "query": query,
            "response_summary": response.summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def get_agents_status(self) -> dict:
        """Get the status of all connected agents."""
        return await self.mcp_client.get_all_agents_status()
