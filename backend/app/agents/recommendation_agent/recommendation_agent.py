"""
Recommendation Agent - MCP Server

Responsibilities:
- Convert climate analysis into practical, actionable recommendations
- Personalize advice based on user type (individual, farmer, business, etc.)
- Prioritize recommendations (immediate, short-term, long-term)
- Ensure recommendations are appropriate and not harmful
- Provide context-sensitive guidance (location, severity)

Tools exposed via MCP:
- generate_recommendations: Main recommendation pipeline
- prioritize_actions: Rank recommendations by urgency/importance
- personalize_advice: Tailor recommendations to user context

Design notes:
- A rule-based template engine always produces sensible, safe recommendations
  keyed off the risk level, the identified hazards, and the user type. This
  guarantees the agent works with zero external dependencies (matching the
  reliability approach of the NLP/Security/Analysis agents).
- When the LLM is available (non-mock) it generates richer, more tailored
  recommendations. Any failure or mock mode falls back to the templates.
- For high/critical risk an emergency_notice is always attached and at least
  one "immediate" action is guaranteed, regardless of the LLM output.

Output contract (consumed by the Orchestrator):
    generate_recommendations -> {
        "recommendations": [
            {"action": str, "priority": str, "explanation": str, "category": str},
            ...
        ],
        "emergency_notice": str | None,
    }
    Priority is one of: "immediate", "short-term", "long-term".

Port: 8105
"""

import json
import logging
import re

from app.mcp.base_agent_server import BaseAgentServer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User-type framing — steers the focus of advice for each audience.
# ---------------------------------------------------------------------------
USER_TYPE_CONTEXT: dict[str, str] = {
    "individual": "personal safety, home protection, emergency kits, evacuation plans",
    "student": "understanding the risk, personal and school safety, community awareness",
    "farmer": "crop protection, irrigation timing, livestock safety, harvest decisions",
    "business": "operations continuity, supply chain, employee safety, asset protection",
    "organization": "infrastructure, community planning, resource allocation, policy response",
    "institution": "infrastructure, continuity planning, occupant safety, coordination with authorities",
}

# ---------------------------------------------------------------------------
# Priority policy per risk level.
#   focus            -> the priority band the advice should lean toward
#   needs_emergency  -> whether an emergency notice + immediate action is required
# ---------------------------------------------------------------------------
RISK_PRIORITY_POLICY: dict[str, dict] = {
    "critical": {"focus": "immediate", "needs_emergency": True},
    "high":     {"focus": "immediate", "needs_emergency": True},
    "moderate": {"focus": "short-term", "needs_emergency": False},
    "low":      {"focus": "long-term", "needs_emergency": False},
    "unknown":  {"focus": "short-term", "needs_emergency": False},
}

# Sort weight for priority bands (used by prioritize_actions).
PRIORITY_WEIGHT: dict[str, int] = {
    "immediate": 0,
    "short-term": 1,
    "long-term": 2,
}

VALID_PRIORITIES = set(PRIORITY_WEIGHT.keys())

# ---------------------------------------------------------------------------
# Hazard-specific action templates. Keyed by hazard label (aligns with the
# Analysis agent's HAZARD_KEYWORDS labels and NLP topic slugs). Each action:
#   (action, base_priority, explanation, category)
# base_priority is later escalated/relaxed to match the risk level.
# ---------------------------------------------------------------------------
HAZARD_ACTIONS: dict[str, list[tuple[str, str, str, str]]] = {
    "flooding": [
        ("Move valuables and important documents to higher ground", "immediate",
         "Flood water can rise quickly and damage belongings.", "protection"),
        ("Avoid crossing flooded roads or fast-moving water on foot or by vehicle", "immediate",
         "Most flood deaths happen when people enter moving water.", "safety"),
        ("Prepare a grab bag with water, medicine, and documents in a waterproof pouch", "short-term",
         "Being ready to leave quickly reduces risk if water rises.", "preparedness"),
        ("Clear drains and gutters around your property before heavy rain", "long-term",
         "Good drainage lowers the chance of local flooding.", "mitigation"),
    ],
    "drought": [
        ("Store and conserve drinking water now", "immediate",
         "Water supplies can become scarce during prolonged dry spells.", "preparedness"),
        ("Prioritize water for essential needs and reduce non-essential use", "short-term",
         "Rationing early makes limited water last longer.", "mitigation"),
        ("Consider drought-tolerant crops and efficient irrigation", "long-term",
         "Reduces vulnerability to future dry seasons.", "mitigation"),
    ],
    "extreme heat": [
        ("Stay hydrated and avoid outdoor activity during peak afternoon heat", "immediate",
         "Heat stress and heatstroke rise sharply in extreme heat.", "safety"),
        ("Check on elderly, children, and outdoor workers", "immediate",
         "Vulnerable people are most at risk during heat waves.", "safety"),
        ("Keep living spaces cool and ventilated", "short-term",
         "A cooler indoor environment reduces heat-related illness.", "protection"),
    ],
    "cyclone / storm": [
        ("Secure loose outdoor objects and reinforce doors and windows", "immediate",
         "High winds turn loose items into dangerous projectiles.", "protection"),
        ("Follow official evacuation orders without delay", "immediate",
         "Timely evacuation is the most effective way to stay safe.", "safety"),
        ("Stock emergency supplies for at least three days", "short-term",
         "Storms can cut power and access to shops for days.", "preparedness"),
    ],
    "landslide": [
        ("Move away from steep slopes and identified landslide-prone areas", "immediate",
         "Landslides can occur suddenly during and after heavy rain.", "safety"),
        ("Watch for warning signs: cracks, tilting trees, sudden water changes", "short-term",
         "Early signs give a short window to move to safety.", "awareness"),
        ("Avoid building or planting on unstable slopes", "long-term",
         "Reduces long-term exposure to slope failure.", "mitigation"),
    ],
    "heavy rainfall": [
        ("Stay indoors and avoid unnecessary travel during heavy rain", "immediate",
         "Reduced visibility and water on roads increase accident risk.", "safety"),
        ("Monitor local weather updates and flood advisories", "short-term",
         "Heavy rain can quickly lead to flooding or landslides.", "awareness"),
    ],
    "coastal / sea-level risk": [
        ("Stay away from the shoreline during high waves or surge warnings", "immediate",
         "Storm surge and high waves are dangerous near the coast.", "safety"),
        ("Plan for coastal flooding if you live in a low-lying area", "short-term",
         "Low-lying coastal zones flood first during surges.", "preparedness"),
    ],
    "poor air quality": [
        ("Limit outdoor exposure and wear a mask if air quality is poor", "immediate",
         "Fine particulates affect the lungs and heart.", "safety"),
        ("Keep windows closed and use air filtration if available", "short-term",
         "Reduces indoor exposure to polluted air.", "protection"),
    ],
    "wildfire": [
        ("Be ready to evacuate and keep an escape route clear", "immediate",
         "Wildfires can spread rapidly and change direction.", "safety"),
        ("Create defensible space by clearing dry vegetation near buildings", "long-term",
         "Reduces the chance of fire reaching structures.", "mitigation"),
    ],
    "soil erosion": [
        ("Avoid disturbing vulnerable soil during heavy rain", "short-term",
         "Exposed soil erodes faster and can destabilize land.", "mitigation"),
        ("Plant ground cover or build terraces on sloped land", "long-term",
         "Vegetation and terracing hold soil in place.", "mitigation"),
    ],
    "crop / agricultural risk": [
        ("Protect or harvest vulnerable crops ahead of the expected event", "immediate",
         "Timely action can save part of the yield.", "protection"),
        ("Adjust planting and irrigation schedules to the forecast", "short-term",
         "Aligning with conditions reduces crop loss.", "mitigation"),
        ("Diversify crops and improve soil health for resilience", "long-term",
         "Diverse, healthy systems withstand climate stress better.", "mitigation"),
    ],
}

# Generic actions used when no specific hazard is identified, keyed by the
# priority band the risk level calls for.
GENERIC_ACTIONS: dict[str, list[tuple[str, str, str, str]]] = {
    "immediate": [
        ("Monitor official weather and disaster-management alerts for your area", "immediate",
         "Staying informed lets you act before conditions worsen.", "awareness"),
        ("Prepare an emergency kit with water, food, first aid, and documents", "immediate",
         "Being ready reduces harm if the situation escalates.", "preparedness"),
        ("Review evacuation routes and emergency contacts", "immediate",
         "Knowing where to go saves critical time in an emergency.", "safety"),
    ],
    "short-term": [
        ("Stay informed about local climate conditions and forecasts", "short-term",
         "Awareness is the first step in preparedness.", "awareness"),
        ("Check and refresh your household emergency supplies", "short-term",
         "Ready supplies help you cope with disruptions.", "preparedness"),
    ],
    "long-term": [
        ("Stay informed about local climate conditions and forecasts", "long-term",
         "Ongoing awareness supports good long-term decisions.", "awareness"),
        ("Review your property and household resilience to climate events", "long-term",
         "Proactive measures reduce future vulnerability.", "mitigation"),
        ("Connect with local disaster-management resources", "long-term",
         "Knowing local resources helps in future events.", "preparedness"),
    ],
}

EMERGENCY_NOTICE = (
    "This situation may pose a serious or immediate risk. Follow instructions "
    "from local authorities and emergency services, and evacuate if advised. "
    "For emergencies, contact your local emergency services immediately."
)


class RecommendationAgent(BaseAgentServer):
    """Recommendation Agent for generating actionable climate guidance."""

    def __init__(self):
        super().__init__(
            name="recommendation_agent",
            port=8105,
            description="Converts analysis into practical, user-appropriate recommendations",
        )

        # Register tools
        self.register_tool(
            "generate_recommendations",
            self.generate_recommendations,
            "Generate actionable recommendations from climate analysis",
        )
        self.register_tool(
            "prioritize_actions",
            self.prioritize_actions,
            "Prioritize and rank recommendations by urgency",
        )
        self.register_tool(
            "personalize_advice",
            self.personalize_advice,
            "Personalize recommendations based on user type and context",
        )

    # =========================================================================
    # Tool: generate_recommendations
    # =========================================================================

    async def generate_recommendations(self, arguments: dict) -> dict:
        """
        Generate practical recommendations from analysis results.

        Input:
            - analysis (dict): Analysis results (risk_level, risk_factors, summary)
            - user_type (str): individual/farmer/business/etc.
            - location (str): User's location

        Output:
            - recommendations (list): [{action, priority, explanation, category}]
            - emergency_notice (str | None)
        """
        analysis = arguments.get("analysis") or {}
        user_type = (arguments.get("user_type") or "individual").lower()
        location = arguments.get("location")

        risk_level = str(analysis.get("risk_level", "unknown")).lower()
        if risk_level not in RISK_PRIORITY_POLICY:
            risk_level = "unknown"
        risk_factors = analysis.get("risk_factors") or []
        policy = RISK_PRIORITY_POLICY[risk_level]

        # 1. Rule-based baseline (always available).
        rule_recs = self._rule_recommendations(risk_level, risk_factors, user_type)

        # 2. Optional LLM enrichment.
        llm_recs = await self._llm_recommendations(
            analysis, risk_level, risk_factors, user_type, location
        )

        recommendations = llm_recs if llm_recs else rule_recs

        # 3. Guarantee an immediate action exists for high/critical risk.
        if policy["needs_emergency"] and not any(
            r["priority"] == "immediate" for r in recommendations
        ):
            recommendations = rule_recs[:1] + recommendations

        # 4. Normalise, dedupe, and order by priority.
        recommendations = self._normalize_recommendations(recommendations)
        recommendations = self._sort_by_priority(recommendations)

        emergency_notice = EMERGENCY_NOTICE if policy["needs_emergency"] else None

        return {
            "recommendations": recommendations,
            "emergency_notice": emergency_notice,
        }

    # =========================================================================
    # Tool: prioritize_actions
    # =========================================================================

    async def prioritize_actions(self, arguments: dict) -> dict:
        """
        Prioritize recommendations by urgency and importance.

        Input:
            - recommendations (list): Raw recommendations
            - risk_level (str): Current risk level

        Output:
            - prioritized (list): Recommendations ordered by priority
        """
        recommendations = arguments.get("recommendations") or []
        risk_level = str(arguments.get("risk_level", "unknown")).lower()

        normalized = self._normalize_recommendations(recommendations)

        # For high/critical risk, promote the first preparedness/safety action
        # to "immediate" if nothing is marked immediate yet.
        policy = RISK_PRIORITY_POLICY.get(risk_level, RISK_PRIORITY_POLICY["unknown"])
        if policy["needs_emergency"] and normalized and not any(
            r["priority"] == "immediate" for r in normalized
        ):
            normalized[0]["priority"] = "immediate"

        return {"prioritized": self._sort_by_priority(normalized)}

    # =========================================================================
    # Tool: personalize_advice
    # =========================================================================

    async def personalize_advice(self, arguments: dict) -> dict:
        """
        Personalize recommendations for the user's context.

        Input:
            - recommendations (list): Generic recommendations
            - user_type (str): User type
            - location (str): Location
            - context (dict): Additional user context

        Output:
            - personalized (list): Tailored recommendations
        """
        recommendations = self._normalize_recommendations(
            arguments.get("recommendations") or []
        )
        user_type = (arguments.get("user_type") or "individual").lower()
        location = arguments.get("location")

        if not recommendations:
            return {"personalized": []}

        # Try LLM personalization; fall back to lightweight rule-based tailoring.
        llm_personalized = await self._llm_personalize(
            recommendations, user_type, location
        )
        if llm_personalized:
            return {"personalized": self._sort_by_priority(llm_personalized)}

        # Rule-based tailoring: append location context to the explanation.
        for rec in recommendations:
            if location and location.lower() not in (rec["explanation"] or "").lower():
                rec["explanation"] = (rec["explanation"] or "").rstrip(".") + f" (relevant for {location})."
        return {"personalized": self._sort_by_priority(recommendations)}

    # =========================================================================
    # Rule-based recommendation engine
    # =========================================================================

    def _rule_recommendations(
        self, risk_level: str, risk_factors: list, user_type: str
    ) -> list[dict]:
        """Build recommendations from hazard templates + generic fallback."""
        policy = RISK_PRIORITY_POLICY[risk_level]
        focus = policy["focus"]
        recs: list[dict] = []

        # Hazard-specific actions for each identified risk factor.
        for factor in risk_factors:
            key = self._match_hazard_key(str(factor))
            if key:
                for action, base_priority, explanation, category in HAZARD_ACTIONS[key]:
                    recs.append({
                        "action": action,
                        "priority": self._adjust_priority(base_priority, focus, risk_level),
                        "explanation": explanation,
                        "category": category,
                    })

        # Always include generic actions matching the focus band so the user has
        # a well-rounded set (and there's a baseline when no hazard matched).
        for action, base_priority, explanation, category in GENERIC_ACTIONS[focus]:
            recs.append({
                "action": action,
                "priority": self._adjust_priority(base_priority, focus, risk_level),
                "explanation": explanation,
                "category": category,
            })

        # Add a user-type-specific framing action.
        framing = USER_TYPE_CONTEXT.get(user_type, USER_TYPE_CONTEXT["individual"])
        article = "an" if user_type[:1] in "aeiou" else "a"
        recs.append({
            "action": f"As {article} {user_type}, focus your preparations on {framing}",
            "priority": focus if focus != "immediate" else "short-term",
            "explanation": "Tailoring actions to your situation makes them more effective.",
            "category": "personalization",
        })

        recs = self._normalize_recommendations(recs)
        # Keep the set focused — cap at 6 recommendations.
        return recs[:6]

    @staticmethod
    def _match_hazard_key(factor: str) -> str | None:
        """Map a free-text risk factor to a HAZARD_ACTIONS key."""
        f = factor.lower().replace("-", " ").strip()
        if f in HAZARD_ACTIONS:
            return f
        # Partial / alias matching against known hazard labels.
        for key in HAZARD_ACTIONS:
            key_head = key.split(" / ")[0]
            if key_head in f or f in key or any(tok in f for tok in key.split()):
                return key
        # Common slug aliases from the NLP/analysis layers.
        aliases = {
            "flood": "flooding",
            "heat wave": "extreme heat",
            "heat-wave": "extreme heat",
            "cyclone": "cyclone / storm",
            "storm": "cyclone / storm",
            "rain": "heavy rainfall",
            "sea level rise": "coastal / sea-level risk",
            "air quality": "poor air quality",
            "agriculture": "crop / agricultural risk",
            "erosion": "soil erosion",
        }
        for alias, key in aliases.items():
            if alias in f:
                return key
        return None

    @staticmethod
    def _adjust_priority(base_priority: str, focus: str, risk_level: str) -> str:
        """
        Escalate template priorities for high/critical risk and relax them for
        low risk, so priorities track the assessed severity.
        """
        if risk_level in ("critical", "high"):
            # An immediate template stays immediate; short-term gets promoted.
            if base_priority == "short-term":
                return "immediate"
            return base_priority
        if risk_level == "low":
            # Relax immediate template actions to short-term for low risk.
            if base_priority == "immediate":
                return "short-term"
            return base_priority
        return base_priority

    # =========================================================================
    # LLM enrichment
    # =========================================================================

    async def _llm_recommendations(
        self, analysis: dict, risk_level: str, risk_factors: list,
        user_type: str, location, 
    ) -> list[dict] | None:
        """Generate recommendations via the LLM. Returns None on unavailable/failure."""
        try:
            from app.services.llm_service import llm_service

            if not llm_service.is_available() or llm_service.get_provider() == "mock":
                return None

            framing = USER_TYPE_CONTEXT.get(user_type, USER_TYPE_CONTEXT["individual"])
            prompt = f"""Generate 3-5 practical climate recommendations.

Analysis summary: {analysis.get('summary', 'N/A')}
Risk level: {risk_level}
Risk factors: {', '.join(str(f) for f in risk_factors) if risk_factors else 'None identified'}
User type: {user_type} (focus on {framing})
Location: {location or 'Not specified'}

Return ONLY a valid JSON object with key "recommendations" containing a list.
Each item must have:
- "action": specific, practical, safe action
- "priority": one of "immediate", "short-term", "long-term"
- "explanation": one short sentence on why it matters
- "category": short label (safety, preparedness, mitigation, awareness, protection)

Match urgency to the risk level. Never recommend anything unsafe. Direct users
to official authorities for emergencies."""

            response = await llm_service.invoke_model(
                prompt=prompt,
                system_prompt="Return ONLY a valid JSON object. No markdown, no code fences, no extra text.",
                max_tokens=700,
                temperature=0.3,
            )

            if not response or response.startswith("[MOCK RESPONSE"):
                return None

            parsed = self._extract_json(response)
            if not parsed:
                return None

            recs = parsed.get("recommendations")
            if isinstance(recs, list) and recs:
                return recs
            return None
        except Exception as exc:
            logger.warning("Recommendation Agent: LLM generation skipped: %s", exc)
            return None

    async def _llm_personalize(
        self, recommendations: list, user_type: str, location
    ) -> list[dict] | None:
        """Rewrite recommendations for the user's context via the LLM."""
        try:
            from app.services.llm_service import llm_service

            if not llm_service.is_available() or llm_service.get_provider() == "mock":
                return None

            framing = USER_TYPE_CONTEXT.get(user_type, USER_TYPE_CONTEXT["individual"])
            recs_json = json.dumps(recommendations, ensure_ascii=False)
            prompt = f"""Rewrite these climate recommendations for a {user_type}
(focus on {framing}){f' in {location}' if location else ''}.
Keep them practical and safe; preserve the JSON structure.

Recommendations: {recs_json}

Return ONLY a valid JSON object with key "recommendations" (same item schema:
action, priority, explanation, category)."""

            response = await llm_service.invoke_model(
                prompt=prompt,
                system_prompt="Return ONLY a valid JSON object. No markdown, no extra text.",
                max_tokens=700,
                temperature=0.3,
            )
            if not response or response.startswith("[MOCK RESPONSE"):
                return None

            parsed = self._extract_json(response)
            if parsed and isinstance(parsed.get("recommendations"), list):
                return self._normalize_recommendations(parsed["recommendations"])
            return None
        except Exception as exc:
            logger.warning("Recommendation Agent: LLM personalization skipped: %s", exc)
            return None

    # =========================================================================
    # Normalisation helpers
    # =========================================================================

    def _normalize_recommendations(self, recommendations: list) -> list[dict]:
        """
        Coerce each recommendation into the standard schema, validate priority,
        and drop duplicates (by action text).
        """
        normalized: list[dict] = []
        seen: set[str] = set()

        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            action = str(rec.get("action", "")).strip()
            if not action:
                continue

            key = action.lower()
            if key in seen:
                continue
            seen.add(key)

            priority = str(rec.get("priority", "short-term")).strip().lower()
            if priority not in VALID_PRIORITIES:
                priority = "short-term"

            normalized.append({
                "action": action,
                "priority": priority,
                "explanation": str(rec.get("explanation", "")).strip(),
                "category": str(rec.get("category", "general")).strip() or "general",
            })

        return normalized

    @staticmethod
    def _sort_by_priority(recommendations: list[dict]) -> list[dict]:
        """Order recommendations immediate -> short-term -> long-term (stable)."""
        return sorted(
            recommendations,
            key=lambda r: PRIORITY_WEIGHT.get(r.get("priority", "short-term"), 1),
        )

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Robustly extract a JSON object from an LLM response string."""
        if not text:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass
        return None


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = RecommendationAgent()
    agent.run()
