"""
Climate Analysis / Risk Agent - MCP Server

Responsibilities:
- Analyze retrieved climate evidence for patterns and trends
- Compare information from multiple sources
- Assess risk level (low, moderate, high, critical) based on defined criteria
- Identify relevant climate hazards for the user's location/situation
- Provide confidence-weighted analysis

Tools exposed via MCP:
- analyze_climate_data: Main analysis pipeline
- assess_risk: Risk level assessment based on evidence
- identify_patterns: Identify trends and patterns in climate data

Design notes:
- The risk engine is rule-based (a severity x probability matrix) so the agent
  always produces a consistent, explainable risk level with zero external
  dependencies. This mirrors how the NLP and Security agents keep a reliable
  deterministic core.
- If the LLM is available (non-mock), it enriches the summary, detailed
  analysis, and claim extraction. Every LLM path degrades gracefully to the
  rule-based result on any failure or in mock mode.
- The rule-based risk level and the LLM-suggested risk level are reconciled by
  taking the more cautious (higher) of the two, so LLM optimism never hides a
  hazard the keyword evidence clearly shows.

Output contract (consumed by the Orchestrator + Verification agent):
    analyze_climate_data -> {
        "summary": str,
        "risk_level": "low" | "moderate" | "high" | "critical" | "unknown",
        "risk_factors": [str, ...],
        "risk_explanation": str,
        "detailed_analysis": str,
        "claims": [str, ...],
        "confidence": float,   # 0-1
    }

Port: 8103
"""

import json
import logging
import re

from app.mcp.base_agent_server import BaseAgentServer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk matrix knowledge banks (module-level so they build once per process)
# ---------------------------------------------------------------------------
#
# Risk score = Severity (1-5) x Probability (1-5)  ->  range 1-25
#   1-6   : low
#   7-12  : moderate
#   13-19 : high
#   20-25 : critical
#
# Severity and probability are each estimated from keyword evidence. Higher
# tiers are checked first so the strongest signal in the text wins.

SEVERITY_KEYWORDS: list[tuple[int, list[str]]] = [
    (5, ["catastrophic", "devastating", "destruction", "collapse", "fatal",
         "deaths", "casualties", "wiped out", "washed away", "state of emergency"]),
    (4, ["severe", "major damage", "widespread", "extensive damage", "displaced",
         "evacuation", "emergency", "critical damage", "life-threatening"]),
    (3, ["significant", "moderate damage", "disruption", "damage to crops",
         "damage to homes", "affected", "hazardous", "flooding of"]),
    (2, ["minor", "localized", "inconvenience", "limited damage", "small-scale",
         "isolated"]),
    (1, ["negligible", "minimal", "no significant", "low impact", "trivial"]),
]

PROBABILITY_KEYWORDS: list[tuple[int, list[str]]] = [
    (5, ["imminent", "currently", "ongoing", "active", "in progress", "now",
         "happening", "underway", "already"]),
    (4, ["very likely", "high probability", "expected", "forecast", "warning issued",
         "will occur", "highly likely", "alert"]),
    (3, ["likely", "moderate probability", "possible", "may occur", "could occur",
         "probable", "anticipated"]),
    (2, ["unlikely", "low probability", "rare", "not expected", "slight chance"]),
    (1, ["very unlikely", "extremely rare", "improbable", "negligible chance"]),
]

# Hazard keywords used to name concrete risk factors found in the evidence.
HAZARD_KEYWORDS: dict[str, list[str]] = {
    "flooding": ["flood", "flooding", "inundation", "overflow", "flash flood",
                 "river discharge", "waterlogging"],
    "drought": ["drought", "dry spell", "water scarcity", "rainfall deficit",
                "water shortage"],
    "extreme heat": ["heat wave", "heatwave", "extreme heat", "heat stress",
                     "high temperature", "heat index"],
    "cyclone / storm": ["cyclone", "storm", "tropical storm", "storm surge",
                        "high winds", "gale", "typhoon"],
    "landslide": ["landslide", "mudslide", "slope failure", "debris flow"],
    "heavy rainfall": ["heavy rain", "downpour", "monsoon", "torrential",
                       "intense rainfall"],
    "coastal / sea-level risk": ["sea level", "coastal erosion", "shoreline",
                                 "tidal flooding", "wave height"],
    "poor air quality": ["air quality", "pm2.5", "pollution", "smog", "aqi"],
    "wildfire": ["wildfire", "forest fire", "bushfire", "fire risk"],
    "soil erosion": ["erosion", "soil erosion", "sediment", "topsoil loss"],
    "crop / agricultural risk": ["crop failure", "harvest loss", "yield decline",
                                 "crop damage", "agricultural loss"],
}

# Numeric-signal patterns that raise probability when live readings look severe.
# Each entry: (regex capturing a number, threshold, probability_floor).
# These let live API readings (e.g. "precipitation probabilities of [80, 90]%")
# influence the assessment even when no strong probability keyword is present.
_HIGH_PRECIP_PROB = re.compile(r"precipitation prob\w*[^0-9]*\[?([0-9]{1,3})", re.IGNORECASE)

# Score band boundaries -> risk level label.
RISK_BANDS: list[tuple[int, str]] = [
    (6, "low"),
    (12, "moderate"),
    (19, "high"),
    (25, "critical"),
]

# Ordering used to reconcile rule-based vs LLM risk levels (take the higher).
RISK_ORDER: dict[str, int] = {
    "unknown": -1,
    "low": 0,
    "moderate": 1,
    "high": 2,
    "critical": 3,
}


class AnalysisAgent(BaseAgentServer):
    """Climate Analysis Agent for risk assessment and pattern identification."""

    def __init__(self):
        super().__init__(
            name="analysis_agent",
            port=8103,
            description="Analyzes retrieved evidence, identifies patterns, and assesses climate risk",
        )

        # Register tools
        self.register_tool(
            "analyze_climate_data",
            self.analyze_climate_data,
            "Main analysis: evaluate evidence, identify hazards, determine risk",
        )
        self.register_tool(
            "assess_risk",
            self.assess_risk,
            "Assess risk level based on evidence and defined criteria",
        )
        self.register_tool(
            "identify_patterns",
            self.identify_patterns,
            "Identify trends and patterns in climate data",
        )

    # =========================================================================
    # Tool: analyze_climate_data
    # =========================================================================

    async def analyze_climate_data(self, arguments: dict) -> dict:
        """
        Main climate data analysis pipeline.

        Input:
            - query (str): Original user query
            - intent (str): Detected intent from NLP agent
            - entities (dict): Extracted entities
            - evidence (list): Retrieved documents from IR agent

        Output:
            - summary (str)
            - risk_level (str): low/moderate/high/critical/unknown
            - risk_factors (list)
            - risk_explanation (str)
            - detailed_analysis (str)
            - claims (list)
            - confidence (float): 0-1
        """
        query = (arguments.get("query") or "").strip()
        entities = arguments.get("entities") or {}
        evidence = arguments.get("evidence") or []

        # No evidence -> unknown risk. Don't fabricate a level.
        if not evidence:
            return {
                "summary": "There is not enough evidence to analyze this climate query.",
                "risk_level": "unknown",
                "risk_factors": [],
                "risk_explanation": "No supporting evidence was retrieved, so a risk level cannot be assigned.",
                "detailed_analysis": None,
                "claims": [],
                "confidence": 0.0,
            }

        # 1. Deterministic risk assessment from the evidence text.
        combined_text = self._combine_evidence_text(evidence)
        rule_assessment = self._assess_risk_from_text(combined_text, entities)

        # 2. Extract concrete risk factors (hazards present in the evidence).
        risk_factors = self._extract_risk_factors(combined_text, entities)
        if not risk_factors and rule_assessment["hazard"]:
            risk_factors = [rule_assessment["hazard"]]

        # 3. Optional LLM enrichment (summary, detailed analysis, claims, risk view).
        llm_result = await self._llm_enrich(query, evidence, rule_assessment)

        # 4. Reconcile risk levels — take the more cautious (higher) of the two.
        rule_level = rule_assessment["risk_level"]
        final_level = rule_level
        if llm_result and llm_result.get("risk_level") in RISK_ORDER:
            llm_level = llm_result["risk_level"]
            final_level = (
                rule_level
                if RISK_ORDER[rule_level] >= RISK_ORDER[llm_level]
                else llm_level
            )

        # 5. Merge LLM-supplied factors/claims with the rule-based factors.
        if llm_result:
            for factor in llm_result.get("risk_factors", []):
                if factor and factor not in risk_factors:
                    risk_factors.append(factor)

        summary = (llm_result or {}).get("summary") or self._rule_summary(
            final_level, risk_factors, entities
        )
        detailed_analysis = (llm_result or {}).get("detailed_analysis") or self._rule_detailed_analysis(
            final_level, risk_factors, evidence, entities
        )
        claims = (llm_result or {}).get("claims") or self._rule_claims(
            final_level, risk_factors, entities, evidence
        )

        risk_explanation = rule_assessment["explanation"]
        if final_level != rule_level:
            risk_explanation += (
                f" Adjusted to '{final_level}' after considering the language and "
                "context of the retrieved evidence."
            )

        # 6. Confidence: driven by evidence volume, source reliability and
        #    whether the rule/LLM assessments agreed.
        confidence = self._compute_confidence(
            evidence, rule_level, final_level, bool(llm_result)
        )

        return {
            "summary": summary,
            "risk_level": final_level,
            "risk_factors": risk_factors,
            "risk_explanation": risk_explanation,
            "detailed_analysis": detailed_analysis,
            "claims": claims,
            "confidence": confidence,
        }

    # =========================================================================
    # Tool: assess_risk
    # =========================================================================

    async def assess_risk(self, arguments: dict) -> dict:
        """
        Assess risk level based on evidence and criteria.

        Input:
            - hazard_type (str, optional)
            - evidence (list): Supporting evidence
            - location (str, optional)
            - timeframe (str, optional)

        Output:
            - risk_level (str)
            - confidence (float)
            - factors (list)
            - severity (int): 1-5
            - probability (int): 1-5
            - risk_score (int): severity x probability
        """
        evidence = arguments.get("evidence") or []
        hazard_type = arguments.get("hazard_type")
        location = arguments.get("location")

        entities: dict = {}
        if hazard_type:
            entities["hazard_type"] = hazard_type
            entities["climate_topic"] = hazard_type
        if location:
            entities["location"] = location

        if not evidence:
            return {
                "risk_level": "unknown",
                "confidence": 0.0,
                "factors": [],
                "severity": 0,
                "probability": 0,
                "risk_score": 0,
            }

        combined_text = self._combine_evidence_text(evidence)
        assessment = self._assess_risk_from_text(combined_text, entities)
        factors = self._extract_risk_factors(combined_text, entities)
        confidence = self._compute_confidence(
            evidence, assessment["risk_level"], assessment["risk_level"], False
        )

        return {
            "risk_level": assessment["risk_level"],
            "confidence": confidence,
            "factors": factors or ([assessment["hazard"]] if assessment["hazard"] else []),
            "severity": assessment["severity"],
            "probability": assessment["probability"],
            "risk_score": assessment["risk_score"],
        }

    # =========================================================================
    # Tool: identify_patterns
    # =========================================================================

    async def identify_patterns(self, arguments: dict) -> dict:
        """
        Identify trends and patterns in climate data.

        Input:
            - data_points (list): Climate data (list of numbers, or list of
              dicts/strings that contain numeric readings)
            - topic (str, optional)

        Output:
            - patterns (list)
            - trend_direction (str): increasing/decreasing/stable/unclear
        """
        data_points = arguments.get("data_points") or []
        topic = arguments.get("topic") or "climate"

        numbers = self._coerce_numbers(data_points)

        if len(numbers) < 2:
            return {
                "patterns": [
                    f"Not enough {topic} data points to establish a reliable trend."
                ],
                "trend_direction": "unclear",
            }

        trend_direction, patterns = self._trend_from_numbers(numbers, topic)
        return {"patterns": patterns, "trend_direction": trend_direction}

    # =========================================================================
    # Rule-based risk engine
    # =========================================================================

    def _assess_risk_from_text(self, text: str, entities: dict) -> dict:
        """
        Run the severity x probability risk matrix over the evidence text.

        Returns a dict with severity, probability, risk_score, risk_level,
        the dominant hazard, and a human-readable explanation.
        """
        text_lower = text.lower()

        severity = self._score_from_keywords(text_lower, SEVERITY_KEYWORDS, default=2)
        probability = self._score_from_keywords(text_lower, PROBABILITY_KEYWORDS, default=2)

        # Numeric overrides from live API readings.
        # These signals lift severity/probability when the live data is clearly
        # significant even if no strong keyword (e.g. "catastrophic") is present.

        # 1. Precipitation probability array — use the MAXIMUM value in the array
        #    so "[98, 41, 84, 99]" registers as 99%, not just the first value 98%.
        precip_probs = re.findall(r'\b(\d{1,3})\b', re.sub(
            r'precipitation prob\w*[^[]*\[([^\]]*)\]',
            lambda m: m.group(1), text, flags=re.IGNORECASE
        ))
        # Simpler fallback: find all numbers after "precipitation prob" keyword
        precip_match = _HIGH_PRECIP_PROB.search(text)
        if precip_match:
            # Grab all numbers in the vicinity (handles array notation)
            vicinity = text[precip_match.start():precip_match.start() + 200]
            all_vals = re.findall(r'\b(\d{1,3})\b', vicinity)
            try:
                max_pct = max(int(v) for v in all_vals if int(v) <= 100)
                if max_pct >= 80:
                    probability = max(probability, 4)
                    # High probability of heavy precipitation also implies higher severity
                    severity = max(severity, 3)
                elif max_pct >= 60:
                    probability = max(probability, 3)
                    severity = max(severity, 2)
            except ValueError:
                pass

        # 2. Daily precipitation totals (mm) — high totals raise severity
        #    e.g. "precipitation totals are [6.8, 5.7, 17.5] mm"
        precip_total_match = re.search(
            r'precipitation totals?\s+(?:are\s+)?\[([^\]]+)\]', text_lower
        )
        if precip_total_match:
            try:
                vals = [float(v) for v in re.findall(r'\d+\.?\d*', precip_total_match.group(1))]
                if vals:
                    max_mm = max(vals)
                    if max_mm >= 30:   # >= 30mm/day → severe rainfall
                        severity = max(severity, 4)
                        probability = max(probability, 3)
                    elif max_mm >= 15:  # >= 15mm/day → significant
                        severity = max(severity, 3)
                        probability = max(probability, 3)
                    elif max_mm >= 5:   # >= 5mm/day → moderate
                        severity = max(severity, 2)
                        probability = max(probability, 2)
            except (ValueError, AttributeError):
                pass

        # 3. River discharge (flood API) — high discharge raises flood severity
        discharge_match = re.search(r'river discharge[^:]*:\s*\[([^\]]+)\]', text_lower)
        if discharge_match:
            try:
                vals = [float(v) for v in re.findall(r'\d+\.?\d*', discharge_match.group(1))]
                if vals:
                    max_discharge = max(vals)
                    if max_discharge >= 1000:
                        severity = max(severity, 4)
                    elif max_discharge >= 500:
                        severity = max(severity, 3)
                    elif max_discharge >= 100:
                        severity = max(severity, 2)
            except (ValueError, AttributeError):
                pass

        risk_score = severity * probability
        risk_level = self._band_for_score(risk_score)

        hazard = self._dominant_hazard(text_lower, entities)

        explanation = (
            f"Assessed severity {severity}/5 and probability {probability}/5 "
            f"(risk score {risk_score}/25), indicating {risk_level} risk"
        )
        if hazard:
            explanation += f" driven primarily by {hazard}."
        else:
            explanation += " based on the retrieved climate evidence."

        return {
            "severity": severity,
            "probability": probability,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "hazard": hazard,
            "explanation": explanation,
        }

    @staticmethod
    def _score_from_keywords(
        text_lower: str, tiers: list[tuple[int, list[str]]], default: int
    ) -> int:
        """Return the highest tier whose keywords appear in the text."""
        for score, keywords in tiers:  # tiers are ordered high -> low
            if any(kw in text_lower for kw in keywords):
                return score
        return default

    @staticmethod
    def _band_for_score(score: int) -> str:
        """Map a 1-25 risk score to a risk-level label."""
        for upper, label in RISK_BANDS:
            if score <= upper:
                return label
        return "critical"

    @staticmethod
    def _dominant_hazard(text_lower: str, entities: dict) -> str:
        """Pick the most relevant hazard name from entities or evidence text."""
        topic = entities.get("climate_topic") or entities.get("hazard_type")
        if topic:
            # Normalise the NLP topic slug (e.g. "sea-level-rise") to a label.
            for label, keywords in HAZARD_KEYWORDS.items():
                if topic.replace("-", " ") in label or any(
                    topic.replace("-", " ") in kw for kw in keywords
                ):
                    return label
            return str(topic).replace("-", " ")

        for label, keywords in HAZARD_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return label
        return ""

    @staticmethod
    def _extract_risk_factors(text_lower_source: str, entities: dict) -> list[str]:
        """List every hazard whose keywords appear in the evidence."""
        text_lower = text_lower_source.lower()
        factors: list[str] = []
        for label, keywords in HAZARD_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                factors.append(label)
        return factors

    # =========================================================================
    # Trend detection
    # =========================================================================

    @staticmethod
    def _coerce_numbers(data_points: list) -> list[float]:
        """Extract a flat list of floats from mixed data-point inputs."""
        numbers: list[float] = []
        for point in data_points:
            if isinstance(point, (int, float)):
                numbers.append(float(point))
            elif isinstance(point, dict):
                for value in point.values():
                    if isinstance(value, (int, float)):
                        numbers.append(float(value))
                        break
            elif isinstance(point, str):
                found = re.findall(r"-?\d+\.?\d*", point)
                if found:
                    try:
                        numbers.append(float(found[0]))
                    except ValueError:
                        pass
        return numbers

    @staticmethod
    def _trend_from_numbers(numbers: list[float], topic: str) -> tuple[str, list[str]]:
        """Determine trend direction and describe it in plain language."""
        first, last = numbers[0], numbers[-1]
        spread = max(numbers) - min(numbers)
        avg = sum(numbers) / len(numbers)

        # A change smaller than 5% of the average (or a tiny absolute spread)
        # is treated as stable to avoid over-reading noise.
        threshold = max(abs(avg) * 0.05, 0.5)
        delta = last - first

        if abs(delta) <= threshold:
            direction = "stable"
            description = f"{topic.capitalize()} readings are relatively stable (change of {delta:+.2f})."
        elif delta > 0:
            direction = "increasing"
            description = f"{topic.capitalize()} shows an increasing trend (from {first:.2f} to {last:.2f})."
        else:
            direction = "decreasing"
            description = f"{topic.capitalize()} shows a decreasing trend (from {first:.2f} to {last:.2f})."

        patterns = [
            description,
            f"Observed range: {min(numbers):.2f} to {max(numbers):.2f} (spread {spread:.2f}), "
            f"average {avg:.2f} across {len(numbers)} data points.",
        ]
        return direction, patterns

    # =========================================================================
    # Rule-based text builders (fallbacks when the LLM is unavailable)
    # =========================================================================

    @staticmethod
    def _rule_summary(risk_level: str, risk_factors: list[str], entities: dict) -> str:
        location = entities.get("location", "the area of interest")
        factors_text = ", ".join(risk_factors) if risk_factors else "climate conditions"
        return (
            f"The retrieved evidence indicates a {risk_level} climate risk for "
            f"{location}, associated with {factors_text}. Review the detailed "
            "analysis and recommendations, and follow official advisories."
        )

    @staticmethod
    def _rule_detailed_analysis(
        risk_level: str, risk_factors: list[str], evidence: list, entities: dict
    ) -> str:
        location = entities.get("location", "the requested location")
        lines = [
            f"Based on {len(evidence)} retrieved source(s), the overall climate "
            f"risk for {location} is assessed as {risk_level}.",
        ]
        if risk_factors:
            lines.append("Key risk factors identified: " + ", ".join(risk_factors) + ".")
        top_sources = [e.get("source_name", "source") for e in evidence[:3]]
        if top_sources:
            lines.append("Primary evidence came from: " + ", ".join(top_sources) + ".")
        lines.append(
            "This assessment reflects the available evidence and should be read "
            "alongside official meteorological and disaster-management guidance."
        )
        return " ".join(lines)

    @staticmethod
    def _rule_claims(
        risk_level: str, risk_factors: list[str], entities: dict, evidence: list
    ) -> list[str]:
        location = entities.get("location", "the area")
        claims = [f"The climate risk for {location} is currently {risk_level}."]
        for factor in risk_factors[:3]:
            claims.append(f"Evidence indicates {factor} is a relevant concern for {location}.")
        return claims

    # =========================================================================
    # LLM enrichment
    # =========================================================================

    async def _llm_enrich(self, query: str, evidence: list, rule_assessment: dict) -> dict | None:
        """
        Ask the LLM to produce a summary, detailed analysis, claims and a
        risk-level opinion grounded in the evidence. Returns None if the LLM is
        unavailable, in mock mode, or fails to return usable JSON.
        """
        try:
            from app.services.llm_service import llm_service

            if not llm_service.is_available() or llm_service.get_provider() == "mock":
                return None

            evidence_text = self._combine_evidence_text(evidence, limit=5, per_doc=500)

            prompt = f"""You are a climate risk analyst. Analyze the query using ONLY the evidence.

USER QUERY: "{query}"

EVIDENCE:
{evidence_text}

A rule-based engine assessed this as {rule_assessment['risk_level']} risk
(severity {rule_assessment['severity']}/5, probability {rule_assessment['probability']}/5).

Return ONLY a valid JSON object with these keys:
- "summary": 2-3 sentence summary grounded in the evidence
- "risk_level": one of "low", "moderate", "high", "critical"
- "risk_factors": list of specific risk factors found in the evidence
- "detailed_analysis": one detailed paragraph
- "claims": list of key factual claims (each independently checkable)

Do not invent data not present in the evidence."""

            response = await llm_service.invoke_model(
                prompt=prompt,
                system_prompt="Return ONLY a valid JSON object. No markdown, no code fences, no extra text.",
                max_tokens=900,
                temperature=0.2,
            )

            if not response or response.startswith("[MOCK RESPONSE"):
                return None

            parsed = self._extract_json(response)
            if not parsed:
                return None

            # Normalise the risk level to our allowed vocabulary.
            level = str(parsed.get("risk_level", "")).strip().lower()
            if level not in RISK_ORDER:
                parsed.pop("risk_level", None)
            else:
                parsed["risk_level"] = level

            # Coerce list-ish fields defensively.
            for key in ("risk_factors", "claims"):
                value = parsed.get(key)
                if isinstance(value, str):
                    parsed[key] = [value]
                elif not isinstance(value, list):
                    parsed[key] = []

            return parsed
        except Exception as exc:
            logger.warning("Analysis Agent: LLM enrichment skipped: %s", exc)
            return None

    # =========================================================================
    # Confidence + helpers
    # =========================================================================

    @staticmethod
    def _compute_confidence(
        evidence: list, rule_level: str, final_level: str, llm_used: bool
    ) -> float:
        """
        Confidence blends evidence volume, mean source reliability, and whether
        the rule-based and LLM assessments agreed.
        """
        if not evidence:
            return 0.0

        # Evidence-volume component (saturates at ~4 sources).
        volume = min(len(evidence) / 4.0, 1.0)

        # Mean source reliability (defaults to 0.6 when absent).
        scores = [
            float(e.get("reliability_score") or 0.6)
            for e in evidence
            if isinstance(e.get("reliability_score", 0.6), (int, float))
        ]
        reliability = sum(scores) / len(scores) if scores else 0.6

        confidence = 0.5 * reliability + 0.3 * volume
        if llm_used:
            # Agreement between rule and LLM raises confidence; disagreement lowers it.
            confidence += 0.2 if rule_level == final_level else 0.05
        else:
            confidence += 0.1  # rule-only still deterministic and explainable

        return round(min(max(confidence, 0.0), 1.0), 2)

    @staticmethod
    def _combine_evidence_text(evidence: list, limit: int = 8, per_doc: int = 600) -> str:
        """Concatenate evidence content into a single text block for scanning."""
        parts: list[str] = []
        for doc in evidence[:limit]:
            name = doc.get("source_name", doc.get("source", "source"))
            content = doc.get("content") or doc.get("snippet") or ""
            parts.append(f"[{name}]: {content[:per_doc]}")
        return "\n".join(parts)

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
    agent = AnalysisAgent()
    agent.run()
