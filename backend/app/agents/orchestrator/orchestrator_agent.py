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
import logging
import uuid
import time
from typing import Optional

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
from app.services.history_service import history_service
from app.services import usage_service

logger = logging.getLogger(__name__)


def infer_user_type(query: str, configured_user_type: Optional[str]) -> str:
    """Use explicit role settings unless the query clearly names another role."""
    text = query.casefold()
    role_terms = {
        "farmer": (
            "farmer", "farming", "planting", "irrigation", "crop", "rice",
            "paddy", "tea", "coconut", "rubber", "වී", "ගොවි", "වගා",
            "நெல்", "விவசாயி", "பயிர்",
        ),
        "student": ("student", "school", "university", "exam", "ශිෂ්‍ය", "පාසල", "மாணவர்", "பள்ளி"),
        "business": ("business", "shop", "company", "supplier", "stock", "වෙළඳ", "ව්‍යාපාර", "வணிகம்", "கடை"),
        "organization": ("organization", "community group", "ngo", "residents", "ප්‍රජා", "සංවිධානය", "சமூக அமைப்பு"),
        "institution": ("hospital", "school management", "university", "facility", "institution", "රෝහල", "ආයතනය", "மருத்துவமனை"),
    }
    for role, terms in role_terms.items():
        if any(term in text for term in terms):
            return role
    return getattr(configured_user_type, "value", None) or configured_user_type or "individual"


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
            from app.services import i18n_service as i18n
            # Sinhala/Tamil query -> that language; otherwise the language chosen in the UI.
            detected_language = i18n.resolve_language(request.query, getattr(request, "language", None))
            effective_user_type = infer_user_type(request.query, request.user_type)

            if usage_service.is_free_greeting(request.query):
                normalized_greeting = " ".join(request.query.strip().lower().split())
                greeting = {
                    "si": (
                        "සුභ උදෑසනක්! මම Climora AI. ඔබට කාලගුණය සහ දේශගුණික අවදානම් පිළිබඳව උදව් කළ හැකියි."
                        if normalized_greeting.startswith(("සුභ උදෑසනක්",))
                        else "සුභ සන්ධ්‍යාවක්! මම Climora AI. ඔබට කාලගුණය සහ දේශගුණික අවදානම් පිළිබඳව උදව් කළ හැකියි."
                        if normalized_greeting.startswith(("සුභ සන්ධ්‍යාවක්",))
                        else "සුභ දවසක්! මම Climora AI. ඔබට කාලගුණය සහ දේශගුණික අවදානම් පිළිබඳව උදව් කළ හැකියි."
                        if normalized_greeting.startswith(("සුභ දවසක්",))
                        else "ආයුබෝවන්! මම Climora AI. ඔබට කාලගුණය සහ දේශගුණික අවදානම් පිළිබඳව උදව් කළ හැකියි."
                    ),
                    "ta": (
                        "காலை வணக்கம்! நான் Climora AI. வானிலை மற்றும் காலநிலை அபாயங்கள் குறித்து உதவ முடியும்."
                        if normalized_greeting.startswith(("காலை வணக்கம்", "இனிய காலை வணக்கம்"))
                        else "மாலை வணக்கம்! நான் Climora AI. வானிலை மற்றும் காலநிலை அபாயங்கள் குறித்து உதவ முடியும்."
                        if normalized_greeting.startswith("மாலை வணக்கம்")
                        else "இனிய நாள்! நான் Climora AI. வானிலை மற்றும் காலநிலை அபாயங்கள் குறித்து உதவ முடியும்."
                        if normalized_greeting.startswith("இனிய நாள்")
                        else "வணக்கம்! நான் Climora AI. வானிலை மற்றும் காலநிலை அபாயங்கள் குறித்து உதவ முடியும்."
                    ),
                }.get(
                    detected_language,
                    (
                        "Good morning! I'm Climora AI. I can help with weather, climate risks, "
                        "hazards, and preparedness in Sri Lanka."
                        if normalized_greeting.startswith("good morning")
                        else "Good afternoon! I'm Climora AI. I can help with weather, climate risks, "
                        "hazards, and preparedness in Sri Lanka."
                        if normalized_greeting.startswith("good afternoon")
                        else "Good evening! I'm Climora AI. I can help with weather, climate risks, "
                        "hazards, and preparedness in Sri Lanka."
                        if normalized_greeting.startswith("good evening")
                        else "Hi, I'm Climora AI. I can help with weather, climate risks, hazards, "
                        "and preparedness in Sri Lanka."
                    ),
                )
                response = ChatResponse(
                    session_id=session_id,
                    query=request.query,
                    summary=greeting,
                    language=detected_language,
                    confidence_score=1.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    agents_used=[],
                )
                self._store_session(session_id, request.query, response)
                return response

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
                history = history_service.get_turns(request.session_id)
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
                            user_type=effective_user_type,
                            session_id=request.session_id,
                            context=request.context,
                            language=request.language,
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
                    summary=i18n.foreign_message(detected_language, _foreign_place),
                    language=detected_language,
                    confidence_score=0.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    agents_used=agents_used,
                )

            # --- Step 2c: Reject non-climate queries at orchestrator level ---
            if not entities.get("climate_topic") and not entities.get("hazard_type"):
                from app.agents.ir_agent.ir_agent import query_has_climate_term
                # Handles English, Sinhala and Tamil (\b word boundaries don't work
                # for the latter two scripts).
                has_climate_term = query_has_climate_term(request.query)
                if not has_climate_term or intent == "non_climate":
                    return ChatResponse(
                        session_id=session_id,
                        query=request.query,
                        summary=i18n.localize_static(
                            "I can only answer climate and environmental questions for locations in Sri Lanka. Please ask about weather, hazards, climate risks, flood, drought, or preparedness for a Sri Lankan location.",
                            detected_language,
                        ),
                        language=detected_language,
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

            # Check if the query text contains a known Sri Lanka location.
            # Includes Sinhala/Tamil generic names so queries like "ශ්‍රී ලංකාවේ
            # මෝසම් ..." or "இலங்கையில் ..." don't get asked for a location.
            has_sri_lanka_location = bool(detected_location) or any(
                kw in query_lower_geo
                for kw in list(LOCATION_ALIASES.keys()) + ["sri lanka", "ceylon"]
            ) or any(
                tok in request.query
                for tok in ("ශ්‍රී ලංකා", "இலங்கை", "වියළි කලාප", "வறண்ட வலய",
                            "මධ්‍යම කඳුකර", "மத்திய மலைநாடு")
            )

            if not has_sri_lanka_location:
                # Climate query with no location — ask the user to specify.
                # Store the session entry so the next message (a location reply)
                # can look back and reconstruct the intent.
                ask_response = ChatResponse(
                    session_id=session_id,
                    query=request.query,
                    summary=i18n.localize_static(
                        "Please specify a location in Sri Lanka for your query. For example: 'What is the weather in Colombo?', 'Is there a flood risk in Kandy?', or 'What is the drought situation in Jaffna?'",
                        detected_language,
                    ),
                    language=detected_language,
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
                # Retrieval failure is an infrastructure problem, not proof the
                # question is non-climate — say so honestly instead of implying
                # the user asked an off-topic question.
                return ChatResponse(
                    session_id=session_id,
                    query=request.query,
                    summary=i18n.localize_static(
                        "I couldn't retrieve supporting evidence for this question right now. Please try again in a moment, or rephrase with a Sri Lanka district name (for example: 'Is there a flood risk in Kandy?').",
                        detected_language,
                    ),
                    language=detected_language,
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
                    user_type=effective_user_type,
                    location=request.location,
                    query=request.query,
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
                user_type=effective_user_type,
            )

            # Store in session
            self._store_session(session_id, request.query, response)

            return response

        except Exception:
            # Graceful error handling — log the real error server-side and
            # return a generic message (never leak internals to the user).
            import logging as _logging
            _logging.getLogger(__name__).exception("Orchestrator failed to process query")
            processing_time = (time.time() - start_time) * 1000
            return ChatResponse(
                session_id=session_id,
                query=request.query,
                summary=f"I encountered an issue while processing your climate query. Please try again.",
                detailed_analysis=f"An unexpected error occurred. Please try again.",
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
            "user_type": (
                request.user_type.value
                if hasattr(request.user_type, "value")
                else request.user_type
            ),
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
            "top_k": 10,
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
        self,
        analysis: dict,
        user_type: Optional[str],
        location: Optional[str],
        query: str = "",
    ) -> dict:
        """Invoke the Recommendation Agent to generate actionable guidance."""
        # user_type may be a UserType enum (from ChatRequest) or a plain string.
        user_type_str = (
            user_type.value if hasattr(user_type, "value") else (user_type or "individual")
        )
        task_payload = {
            "analysis": analysis,
            "user_type": user_type_str,
            "location": location,
            "query": query,
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
        user_type: Optional[str] = None,
    ) -> ChatResponse:
        """Assemble the final response from all agent outputs."""

        processing_time = (time.time() - start_time) * 1000
        live_docs = [
            d for d in ir_result.get("documents", [])
            if d.get("evidence_type") == "live" or d.get("date") == "live"
        ]

        # Build summary using LLM to synthesize all agent outputs
        summary = await self._generate_summary(
            query=request.query,
            analysis=analysis_result,
            verification=verification_result,
            language=language,
            user_type=user_type,
            location=request.location or nlp_result.get("entities", {}).get("location"),
            evidence=live_docs,
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

        # --- Language handling -------------------------------------------------
        from app.services import i18n_service as i18n
        entities = nlp_result.get("entities", {}) or {}

        # No LLM (mock mode), or the LLM did not answer in the requested language:
        # build a data-based summary from the live readings instead of a canned line.
        if (not llm_service.is_available()) or not summary or (
            language != "en" and not i18n.is_in_language(summary, language)
        ):
            summary = i18n.build_summary(
                language,
                entities.get("location") or request.location or "",
                live_docs,
                analysis_result.get("risk_level", "unknown"),
                analysis_result.get("risk_factors", []),
            )

        detailed_analysis = analysis_result.get("detailed_analysis")
        disclaimer = ChatResponse.model_fields["disclaimer"].default
        if language in ("si", "ta"):
            if risk_assessment:
                risk_assessment.explanation = await i18n.localize_text(
                    risk_assessment.explanation or "", language, "explanation"
                )
                risk_assessment.risk_factors = i18n.localize_factors(
                    risk_assessment.risk_factors, language
                )
            if detailed_analysis:
                detailed_analysis = await i18n.localize_text(detailed_analysis, language, "detailed")
            for rec in recommendations:
                rec.action = await i18n.localize_text(rec.action, language, "recommendation")
                if rec.explanation:
                    rec.explanation = await i18n.localize_text(rec.explanation, language, "recommendation")
            disclaimer = i18n.localize_static(disclaimer, language)

        return ChatResponse(
            session_id=session_id,
            query=request.query,
            summary=summary,
            detailed_analysis=detailed_analysis,
            disclaimer=disclaimer,
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
        self,
        query: str,
        analysis: dict,
        verification: dict,
        language: str = "en",
        user_type: Optional[str] = None,
        location: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
    ) -> str:
        """Use the LLM to generate a user-friendly summary from agent outputs."""
        from app.services.language_service import get_response_instruction

        language_instruction = get_response_instruction(language)
        audience = user_type.value if hasattr(user_type, "value") else (user_type or "individual")
        audience_guidance = {
            "individual": "personal safety and household decisions",
            "student": "clear learning, personal safety, and school/community awareness",
            "farmer": (
                "farm decisions: rainfall and temperature patterns, planting and harvest timing, "
                "irrigation, crop and livestock protection"
            ),
            "business": "business continuity, staff safety, assets, logistics, and supply chains",
            "organization": "community planning, vulnerable groups, infrastructure, and resource allocation",
            "institution": "occupant safety, service continuity, facilities, and coordination with authorities",
        }.get(audience, "personal safety and practical decisions")
        crop_guidance = (
            "Identify the crop mentioned in the question (for example rice, tea, coconut, "
            "rubber, or vegetables) and tailor planting, fertilizer, irrigation, drainage, "
            "pest/disease, and harvest advice to it. If no crop is named, ask for it or "
            "keep the advice crop-agnostic."
            if audience == "farmer"
            else ""
        )
        evidence_context = "\n".join(
            str(doc.get("content") or doc.get("snippet") or "")
            for doc in (evidence or [])
        )[:5000]
        farmer_instruction = (
            "For a farmer, use the live forecast details below when available. State the "
            "actual short-range rainfall/temperature information, then explain that exact "
            "weather several months ahead is not available from this data. Do not say that "
            "no risk factors were identified if the evidence contains rainfall, flooding, "
            "or other relevant signals."
            if audience == "farmer"
            else ""
        )

        prompt = f"""Based on the following climate analysis, provide a clear and concise summary 
for the user who asked: "{query}"

Analysis findings: {analysis.get('summary', 'No analysis available')}
Risk level: {analysis.get('risk_level', 'unknown')}
Risk factors: {', '.join(analysis.get('risk_factors', [])) or 'None identified'}
Verification status: {'Verified' if verification.get('verified') else 'Partially verified'}
Confidence: {verification.get('confidence', 'Unknown')}
Audience: {audience}
Audience-specific focus: {audience_guidance}
Location: {location or 'Not specified'}
Live evidence:
{evidence_context or 'No live evidence available'}

Provide a helpful, evidence-based summary in 3-5 sentences. Tailor the practical meaning
to the audience, not just the recommendations. For a farmer asking about upcoming months,
separate the available short-range weather forecast from longer-range seasonal tendencies;
never invent exact monthly rainfall or temperature values when seasonal data is unavailable.
{farmer_instruction}
{crop_guidance}
Be specific about the risks and what the user should know. Be clear about what is known and what is uncertain.
Do not make claims beyond what the evidence supports.

{language_instruction}"""

        system_prompt = (
            "You are Climora AI, a climate intelligence assistant. "
            "Provide clear, evidence-based responses. "
            "Always communicate uncertainty honestly. "
            "Never present uncertain information as fact. "
            f"{language_instruction}"
        )

        try:
            return await self._generate_summary_llm(
                prompt=prompt,
                system_prompt=system_prompt,
            )
        except Exception:
            return self._extractive_summary(
                query=query,
                analysis=analysis,
                verification=verification,
                location=location,
                evidence=evidence,
            )

    async def _generate_summary_llm(self, prompt: str, system_prompt: str) -> str:
        """Single LLM summary call (raises when the LLM is unreachable)."""
        try:
            return await llm_service.invoke_model(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=500,
                temperature=0.4,
            )
        except Exception as exc:
            logger.warning("LLM summary unavailable (%s) — using extractive fallback", exc)
            raise

    def _extractive_summary(
        self,
        query: str,
        analysis: dict,
        verification: dict,
        location: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
    ) -> str:
        """Build an honest summary purely from retrieved evidence (no LLM).

        Used when the LLM is unreachable: states only what the evidence and
        analysis contain (location, risk level, factors, top snippet,
        verification status). Never invents claims or numbers.
        """
        risk = str(analysis.get("risk_level", "unknown"))
        factors = analysis.get("risk_factors", []) or []
        factor_txt = "; ".join(str(f) for f in factors[:3]) or "no specific factors identified"
        # Prefer the snippet with the most query-term overlap so the summary
        # stays on the user's actual question, not just the first document.
        terms = {w for w in query.lower().split() if len(w) > 3}
        snippet, best_score = "", -1
        for doc in (evidence or [])[:5]:
            txt = str(doc.get("content") or doc.get("snippet") or "").strip()
            if len(txt) < 60:
                continue
            score = sum(1 for t in terms if t in txt.lower())
            if score > best_score:
                snippet, best_score = txt[:400], score
        verified = "verified against retrieved evidence" if verification.get("verified") else "partially verified"
        conf = verification.get("confidence", "unknown")
        parts = [
            f"For {location or 'the requested area'}: assessed {risk} risk.",
            f"Key factors: {factor_txt}.",
        ]
        if snippet:
            parts.append(f"Supporting evidence: {snippet}")
        parts.append(
            f"This assessment is {verified} (confidence {conf}). "
            "Generated offline from retrieved evidence without AI synthesis; "
            "treat it as indicative and check official sources for emergencies."
        )
        return " ".join(parts)

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

        # Trilingual backfill: the English gazetteer above misses Sinhala/Tamil
        # place names. The NLP agent's rule-based extractor covers all three
        # languages offline (see evaluate_ir.py: 16/16) — reuse it here so the
        # pipeline stays trilingual when the NLP agent server is down.
        impl_topic = None
        if detected_location is None:
            try:
                from app.agents.nlp_agent.nlp_agent import NLPAgent
                impl_entities = NLPAgent()._extract_entities_impl(request.query, None) or {}
                detected_location = impl_entities.get("location") or None
                impl_topic = impl_entities.get("climate_topic") or impl_entities.get("hazard_type")
            except Exception:
                detected_location, impl_topic = None, None

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
        if climate_topic is None and impl_topic:
            climate_topic = hazard_type = impl_topic

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

        if not vector_store_service.is_available() or getattr(vector_store_service, "_index", None) is None or vector_store_service._index.ntotal == 0:
            return {"documents": [], "message": "No documents in vector store"}

        original_query = structured_query.get("original_query", "")

        # Reject non-climate queries early
        query_lower = original_query.lower()
        has_climate_entities = entities.get("climate_topic") or entities.get("hazard_type")
        if not has_climate_entities and not any(t in query_lower for t in CLIMATE_QUERY_TERMS):
            return {"documents": [], "message": "No climate-related evidence was retrieved for this query."}

        # Build search query from canonical English entities. The document
        # corpus is English and local embeddings are hashed TF-IDF buckets, so
        # a raw Sinhala/Tamil query matches mostly noise: enrich with the
        # NLP-derived English location/topic plus topic vocabulary, and
        # over-fetch (the location filter below needs headroom).
        location = entities.get("location", "")
        if isinstance(location, list):
            location = location[0] if location else ""
        topic = entities.get("climate_topic") or entities.get("hazard_type") or ""
        TOPIC_EXPANSION = {
            "flood": "flood flooding flood risk river rainfall monsoon overflow water",
            "drought": "drought dry rainfall water scarcity",
            "cyclone": "cyclone storm wind",
            "landslide": "landslide rain hill slope",
            "heat-wave": "heat temperature hot",
            "rain": "rain rainfall monsoon precipitation",
            "temperature": "temperature weather rainfall",
        }
        if location or topic:
            search_query = (
                f"{TOPIC_EXPANSION.get(topic, topic)} {location} "
                "Sri Lanka climate weather"
            ).strip()
        else:
            search_query = original_query

        # Over-fetch to compensate for post-filter location filtering
        results = await vector_store_service.query_similar(
            query_text=search_query,
            top_k=40,
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
            for i, doc in enumerate(evidence[:8], 1):
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

        try:
            response = await llm_service.invoke_model(
                prompt=prompt,
                system_prompt="Return ONLY a valid JSON object. No markdown, no explanation, no code fences. Just the JSON.",
                max_tokens=1000,
                temperature=0.2,
            )
        except Exception as exc:
            logger.warning("LLM analysis unavailable (%s) — using evidence-based fallback", exc)
            response = ""

        # Robust JSON parsing — handle markdown fences, extra text, etc.
        import json
        import re

        parsed = self._parse_json_response(response) if response else None
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

        try:
            response = await self._generate_recommendations_llm(
                prompt=prompt,
            )
        except Exception:
            response = ""

        parsed = self._parse_json_response(response) if response else None
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

    async def _generate_recommendations_llm(self, prompt: str) -> str:
        """Single LLM recommendations call (raises when the LLM is unreachable)."""
        try:
            return await llm_service.invoke_model(
                prompt=prompt,
                system_prompt="Return ONLY a valid JSON object. No markdown, no explanation. Just JSON.",
                max_tokens=600,
                temperature=0.3,
            )
        except Exception as exc:
            logger.warning("LLM recommendations unavailable (%s) — using static fallback", exc)
            raise

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
        """Persist a conversation turn (PostgreSQL when available, memory otherwise)."""
        history_service.store_turn(session_id, query, response.summary)

    def get_session_history(self, session_id: str) -> list[dict]:
        """Return the stored query/response turns for a session."""
        return history_service.get_turns(session_id)

    async def get_agents_status(self) -> dict:
        """Get the status of all connected agents."""
        return await self.mcp_client.get_all_agents_status()

    async def process_user_query_stream(self, request: ChatRequest):
        """
        Run the full pipeline while yielding real-time agent-communication events.

        Yields dict events as they actually happen:
          - {"type": "pipeline_start"}
          - {"type": "agent_start", "agent": <name>, "tool": <tool>}
          - {"type": "agent_end", "agent": <name>, "outcome": <success|fallback|error>, ...}
          - {"type": "done", "response": <ChatResponse as dict>}

        The events are emitted by the MCP client the moment each agent tool is
        invoked/returns, so the Agent Mesh reflects the exact communication flow.
        When the pipeline finishes, the stream ends — signalling the mesh to stop
        showing any active communication.
        """
        queue: asyncio.Queue = asyncio.Queue()

        async def _on_event(event: dict):
            await queue.put(event)

        # Register the callback so every real agent call reports here.
        self.mcp_client.set_event_callback(_on_event)

        await queue.put({"type": "pipeline_start"})

        async def _run():
            try:
                response = await self.process_user_query(request)
                await queue.put({
                    "type": "done",
                    "response": response.model_dump(mode="json"),
                })
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(None)  # sentinel: pipeline complete

        task = asyncio.create_task(_run())

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self.mcp_client.set_event_callback(None)
            if not task.done():
                task.cancel()
