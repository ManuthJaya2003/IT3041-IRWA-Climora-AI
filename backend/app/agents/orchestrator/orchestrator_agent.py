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

import uuid
import time
from typing import Optional
from datetime import datetime

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
from app.services.bedrock_service import bedrock_service


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
            # --- Step 1: Security Validation ---
            security_result = await self._invoke_security_agent(request)
            agents_used.append("security_agent")

            if not security_result.get("safe", True):
                return self._build_blocked_response(
                    session_id, request.query, security_result.get("reason", "Request blocked")
                )

            # --- Step 2: NLP Processing ---
            nlp_result = await self._invoke_nlp_agent(request)
            agents_used.append("nlp_agent")

            structured_query = nlp_result.get("structured_query", {})
            intent = nlp_result.get("intent", "general_climate_query")
            entities = nlp_result.get("entities", {})

            # --- Step 3: Information Retrieval ---
            ir_result = await self._invoke_ir_agent(structured_query, entities)
            agents_used.append("ir_agent")

            retrieved_evidence = ir_result.get("documents", [])

            # --- Step 4: Climate Analysis ---
            analysis_result = await self._invoke_analysis_agent(
                query=request.query,
                intent=intent,
                entities=entities,
                evidence=retrieved_evidence,
            )
            agents_used.append("analysis_agent")

            # --- Step 5: Verification ---
            verification_result = await self._invoke_verification_agent(
                claims=analysis_result.get("claims", []),
                sources=retrieved_evidence,
            )
            agents_used.append("verification_agent")

            # --- Step 6: Recommendations ---
            recommendation_result = await self._invoke_recommendation_agent(
                analysis=analysis_result,
                user_type=request.user_type,
                location=request.location,
            )
            agents_used.append("recommendation_agent")

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

        return result if result else {"safe": True, "reason": "Security agent unavailable - allowing request"}

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

        if result:
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

        if result:
            return result

        # Fallback: return empty evidence
        return {"documents": [], "message": "IR agent unavailable"}

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

        if result:
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

        if result:
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

        if result:
            return result

        # Fallback
        return {
            "recommendations": [
                {
                    "action": "Stay informed about local climate conditions",
                    "priority": "short-term",
                    "explanation": "Recommendation agent unavailable - providing general guidance.",
                }
            ]
        }

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
    ) -> ChatResponse:
        """Assemble the final response from all agent outputs."""

        processing_time = (time.time() - start_time) * 1000

        # Build summary using LLM to synthesize all agent outputs
        summary = await self._generate_summary(
            query=request.query,
            analysis=analysis_result,
            verification=verification_result,
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

        # Build sources list
        sources = [
            SourceEvidence(
                source_name=doc.get("source_name", "Unknown Source"),
                source_url=doc.get("url"),
                content_snippet=doc.get("snippet", doc.get("content", "")[:200]),
                reliability_score=doc.get("reliability_score"),
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
            confidence_score=confidence,
            processing_time_ms=processing_time,
            agents_used=agents_used,
        )

    async def _generate_summary(
        self, query: str, analysis: dict, verification: dict
    ) -> str:
        """Use the LLM to generate a user-friendly summary from agent outputs."""
        prompt = f"""Based on the following climate analysis, provide a clear and concise summary 
for the user who asked: "{query}"

Analysis findings: {analysis.get('summary', 'No analysis available')}
Verification status: {'Verified' if verification.get('verified') else 'Partially verified'}
Confidence: {verification.get('confidence', 'Unknown')}

Provide a helpful, evidence-based summary in 2-3 sentences. Be clear about what is known 
and what is uncertain. Do not make claims beyond what the evidence supports."""

        system_prompt = (
            "You are Climora AI, a climate intelligence assistant. "
            "Provide clear, evidence-based responses. "
            "Always communicate uncertainty honestly. "
            "Never present uncertain information as fact."
        )

        response = await bedrock_service.invoke_model(
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
        """Fallback NLP processing using LLM directly."""
        prompt = f"""Analyze the following climate-related query and extract:
1. The user's intent (e.g., risk_awareness, forecast, preparedness, general_info)
2. Key entities (location, time_period, climate_topic, hazard_type)
3. A structured version of the query for information retrieval

Query: "{request.query}"
Location provided: {request.location or 'Not specified'}

Respond in JSON format with keys: intent, entities, structured_query, expanded_terms"""

        response = await bedrock_service.invoke_model(
            prompt=prompt,
            system_prompt="You are an NLP processing module. Return only valid JSON.",
            max_tokens=500,
            temperature=0.2,
        )

        # Try to parse JSON, fallback to basic structure
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return {
                "intent": "general_climate_query",
                "entities": {"location": request.location},
                "structured_query": {"original_query": request.query},
                "expanded_terms": [],
            }

    async def _fallback_analysis(self, query: str, evidence: list) -> dict:
        """Fallback analysis using LLM directly."""
        prompt = f"""Analyze the following climate query and any available evidence:

Query: "{query}"
Evidence: {evidence[:3] if evidence else 'No evidence available'}

Provide:
1. A brief analysis summary
2. Risk level (low, moderate, high, critical, or unknown)
3. Key risk factors
4. Detailed analysis

Respond in JSON format with keys: summary, risk_level, risk_factors, detailed_analysis, claims"""

        response = await bedrock_service.invoke_model(
            prompt=prompt,
            system_prompt="You are a climate analysis module. Return only valid JSON.",
            max_tokens=800,
            temperature=0.3,
        )

        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return {
                "summary": "Analysis unavailable - insufficient data.",
                "risk_level": "unknown",
                "risk_factors": [],
                "detailed_analysis": None,
                "claims": [],
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
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def get_agents_status(self) -> dict:
        """Get the status of all connected agents."""
        return await self.mcp_client.get_all_agents_status()
