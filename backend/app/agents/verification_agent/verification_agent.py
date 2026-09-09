"""
Verification / Evidence Agent - MCP Server

Responsibilities:
- Check source quality and reliability
- Verify whether claims are supported by retrieved evidence
- Cross-reference claims across multiple sources
- Flag uncertain, conflicting, or unsupported information
- Assign confidence scores to claims
- Check information freshness (timestamps, currency)

Tools exposed via MCP:
- verify_claims: Main verification pipeline
- check_source_quality: Evaluate source reliability
- cross_reference: Compare claims across sources

Why this agent exists:
- Climate information can be time-sensitive and high-impact
- LLMs may hallucinate or make unsupported claims
- Users need to trust the information for decision-making
- Responsible AI requires grounding outputs in evidence

Tech:
- LLM (via Bedrock/Gemini fallback) for claim-evidence comparison
- Source reliability database/rules
- Timestamp checking for freshness
- Cross-referencing logic

Port: 8104
"""

import json
import logging
import re
from datetime import datetime
from app.mcp.base_agent_server import BaseAgentServer
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from an LLM response string.

    Tries direct parse first, then strips markdown fences, then uses a
    regex to find the first {...} block in the text. Raises ValueError
    if no valid JSON object can be found.
    """
    # 1. Direct parse (response is already clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip common markdown fences and retry
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Regex extraction — find the outermost { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON object found in LLM response: {text[:200]!r}")


class VerificationAgent(BaseAgentServer):
    """Verification Agent for checking claims, sources, and evidence quality."""

    # Trusted domain and source authority scores database
    HIGH_TRUST_SOURCES = {
        "wmo": {"score": 0.98, "category": "international_agency"},
        "world meteorological organization": {"score": 0.98, "category": "international_agency"},
        "department of meteorology sri lanka": {"score": 0.95, "category": "government_meteorological"},
        "met department": {"score": 0.95, "category": "government_meteorological"},
        "disaster management centre": {"score": 0.95, "category": "government_disaster_agency"},
        "sri lanka disaster management centre": {"score": 0.95, "category": "government_disaster_agency"},
        "noaa": {"score": 0.96, "category": "government_agency"},
        "irrigation department sri lanka": {"score": 0.92, "category": "government_agency"},
        "coast conservation department": {"score": 0.92, "category": "government_agency"},
        "mahaweli authority of sri lanka": {"score": 0.90, "category": "government_agency"},
        "water supply and drainage board sri lanka": {"score": 0.90, "category": "government_utility"},
        # Fixed: was "openopenweathermap api" (double "open") — never matched the IR agent's source name
        "openweathermap api": {"score": 0.90, "category": "live_weather_api"},
        "open-meteo climate api": {"score": 0.90, "category": "live_weather_api"},
        "open-meteo flood api": {"score": 0.90, "category": "live_hydrology_api"},
        "open-meteo air quality api": {"score": 0.90, "category": "live_air_quality_api"},
        "open-meteo marine api": {"score": 0.90, "category": "live_marine_api"},
        "university of moratuwa": {"score": 0.88, "category": "academic"},
        "tea research institute of sri lanka": {"score": 0.88, "category": "academic_research"},
    }

    def __init__(self):
        super().__init__(
            name="verification_agent",
            port=8104,
            description="Checks source quality, claim-evidence support, and cross-references information",
        )

        # Register tools
        self.register_tool(
            "verify_claims",
            self.verify_claims,
            "Verify whether claims are supported by retrieved evidence",
        )
        self.register_tool(
            "check_source_quality",
            self.check_source_quality,
            "Evaluate the quality and reliability of a source",
        )
        self.register_tool(
            "cross_reference",
            self.cross_reference,
            "Cross-reference claims across multiple sources",
        )

    async def verify_claims(self, arguments: dict) -> dict:
        """
        Main claim verification pipeline.

        Input:
            - claims (list): Claims from the analysis agent to verify
            - sources (list): Retrieved sources/evidence

        Output:
            - verified (bool): Overall verification status
            - confidence (float): Overall confidence in the information (0-1)
            - claim_results (list): Per-claim verification results
            - warnings (list): Critical issues (unsupported/contradicted claims)
            - info (list): Informational notes (e.g. stale sources) that do not
                          fail overall verification on their own
        """
        claims = arguments.get("claims", [])
        sources = arguments.get("sources", [])

        # Normalise a bare string claim to a list
        if isinstance(claims, str):
            claims = [claims]

        if not claims:
            return {
                "verified": False,
                "confidence": 0.0,
                "claim_results": [],
                "warnings": ["No claims were provided for verification."],
                "info": [],
            }

        # Warn early when no evidence was provided — don't silently run LLM
        # against a placeholder string and return spuriously low confidence.
        if not sources:
            return {
                "verified": False,
                "confidence": 0.0,
                "claim_results": [
                    {
                        "claim": str(c),
                        "status": "unverifiable",
                        "confidence": 0.0,
                        "explanation": "No evidence sources were provided for verification.",
                    }
                    for c in claims
                ],
                "warnings": ["No evidence sources were provided — claims cannot be verified."],
                "info": [],
            }

        claim_results = []
        # Separate critical warnings from informational notes so a stale-source
        # note does not cause the whole response to return verified=False.
        critical_warnings: list[str] = []
        info_notes: list[str] = []
        total_confidence = 0.0

        # Build context block out of sources/evidence
        evidence_texts = []
        for src in sources:
            name = src.get("source_name", src.get("source", "Unknown"))
            content = src.get("content", src.get("snippet", ""))
            evidence_texts.append(f"[{name}]: {content}")

        combined_evidence = "\n".join(evidence_texts)

        for claim in claims:
            claim_str = str(claim)

            # Attempt LLM-based verification prompt
            prompt = f"""
You are a rigorous Fact-Checking & Climate Verification Agent.
Evaluate if the following CLAIM is strictly supported by the provided EVIDENCE.

CLAIM: "{claim_str}"

EVIDENCE:
{combined_evidence}

Respond ONLY in valid raw JSON with the following structure:
{{
    "status": "supported" | "partially_supported" | "unsupported" | "contradicted",
    "confidence": <float 0.0 to 1.0>,
    "explanation": "<short explanation>"
}}
"""

            try:
                llm_response = await llm_service.generate_text(prompt=prompt)
                parsed = _extract_json(llm_response)

                status = parsed.get("status", "partially_supported")
                conf = float(parsed.get("confidence", 0.7))
                exp = parsed.get("explanation", "Verified against provided evidence.")

            except Exception as exc:
                logger.warning("LLM verification failed for claim '%s': %s", claim_str[:60], exc)
                # Rule-based / keyword fallback when LLM is unavailable or returns bad JSON
                matches = sum(
                    1 for src in sources
                    if any(
                        word in src.get("content", "").lower()
                        for word in claim_str.lower().split()
                        if len(word) > 3
                    )
                )
                if matches >= 2:
                    status = "supported"
                    conf = 0.85
                    exp = "Claim supported by key evidence terms."
                elif matches == 1:
                    status = "partially_supported"
                    conf = 0.60
                    exp = "Partial overlap found in evidence."
                else:
                    status = "unsupported"
                    conf = 0.30
                    exp = "No direct evidence matching claim key terms."

            claim_results.append({
                "claim": claim_str,
                "status": status,
                "confidence": conf,
                "explanation": exp,
            })

            total_confidence += conf
            if status in ("unsupported", "contradicted"):
                critical_warnings.append(f"Claim '{claim_str[:60]}...' is {status}.")

        overall_confidence = round(total_confidence / len(claims), 2) if claims else 0.0
        # Only fail verification on critical issues (unsupported/contradicted claims).
        # Informational notes like stale sources are reported separately.
        overall_verified = overall_confidence >= 0.65 and len(critical_warnings) == 0

        # Source freshness check — uses year-diff logic, not hardcoded year string
        current_year = datetime.now().year
        for src in sources:
            date_str = str(src.get("date", src.get("content_date", "")) or "")
            if not date_str or date_str in ("live", "current", "today"):
                continue
            # Extract the first 4-digit year found in the date string
            year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
            if year_match:
                pub_year = int(year_match.group())
                diff = current_year - pub_year
                if diff > 3:
                    info_notes.append(
                        f"Source '{src.get('source_name', 'Unknown')}' contains data from "
                        f"{pub_year} ({diff} years ago) — treat as historical context."
                    )
                elif diff > 1:
                    info_notes.append(
                        f"Source '{src.get('source_name', 'Unknown')}' data is {diff} year(s) old."
                    )

        return {
            "verified": overall_verified,
            "confidence": overall_confidence,
            "claim_results": claim_results,
            "warnings": critical_warnings,
            "info": info_notes,
        }

    async def check_source_quality(self, arguments: dict) -> dict:
        """
        Evaluate source reliability.

        Input:
            - source_name (str): Name of the source
            - source_url (str): URL of the source
            - content_date (str): When the content was published

        Output:
            - reliability_score (float): 0-1 reliability rating
            - category (str): Type of source (government, academic, news, etc.)
            - freshness (str): How current the information is
            - notes (str): Any concerns about the source
        """
        source_name = str(arguments.get("source_name") or "").strip().lower()
        source_url = str(arguments.get("source_url") or "").lower()
        content_date = arguments.get("content_date") or "live"

        reliability_score = 0.70
        category = "general_media"
        notes = "Standard source."

        # Rule matching against high trust database
        for key, info in self.HIGH_TRUST_SOURCES.items():
            if key in source_name or key in source_url:
                reliability_score = info["score"]
                category = info["category"]
                notes = "High authority recognised climate institution."
                break

        if ".gov" in source_url or ".gov.lk" in source_url:
            reliability_score = max(reliability_score, 0.90)
            category = "government_portal"
            notes = "Official government domain."
        elif ".edu" in source_url or ".ac.lk" in source_url:
            reliability_score = max(reliability_score, 0.88)
            category = "academic"
            notes = "Accredited educational/academic research domain."

        # Freshness evaluation
        freshness = "unknown"
        if str(content_date).lower() in ("live", "current", "today"):
            freshness = "real_time"
        else:
            try:
                year_match = re.search(r"\b(19|20)\d{2}\b", str(content_date))
                if year_match:
                    pub_year = int(year_match.group())
                    current_year = datetime.now().year
                    diff = current_year - pub_year
                    if diff <= 1:
                        freshness = "current"
                    elif diff <= 3:
                        freshness = "recent"
                    else:
                        freshness = "historical"
                        notes += f" Note: Historical data ({diff} years old)."
                else:
                    freshness = "recent"
            except Exception:
                freshness = "recent"

        return {
            "reliability_score": reliability_score,
            "category": category,
            "freshness": freshness,
            "notes": notes,
        }

    async def cross_reference(self, arguments: dict) -> dict:
        """
        Cross-reference a claim across multiple sources using LLM-based evaluation.

        Input:
            - claim (str): The claim to cross-reference
            - sources (list): Sources to check against

        Output:
            - supported_by (list): Sources that support the claim
            - contradicted_by (list): Sources that contradict the claim
            - not_mentioned_in (list): Sources that don't cover it
            - consensus_score (float): Agreement ratio across sources (0-1)
        """
        claim = arguments.get("claim", "")
        sources = arguments.get("sources", [])

        supported_by: list[str] = []
        contradicted_by: list[str] = []
        not_mentioned_in: list[str] = []

        for src in sources:
            src_name = src.get("source_name", src.get("source", "Unknown Source"))
            content = src.get("content", src.get("snippet", "")).strip()

            if not content:
                not_mentioned_in.append(src_name)
                continue

            # LLM-based per-source evaluation — detects negation and contradictions
            prompt = f"""
You are a climate fact-checker. Does the following SOURCE CONTENT support, contradict,
or not mention the CLAIM? Answer precisely.

CLAIM: "{claim}"

SOURCE ({src_name}):
{content[:1000]}

Respond ONLY in valid raw JSON:
{{
    "verdict": "supports" | "contradicts" | "not_mentioned",
    "reason": "<one sentence>"
}}
"""
            verdict = "not_mentioned"
            try:
                llm_response = await llm_service.generate_text(prompt=prompt)
                parsed = _extract_json(llm_response)
                verdict = parsed.get("verdict", "not_mentioned")
            except Exception as exc:
                logger.warning(
                    "LLM cross-reference failed for source '%s': %s — falling back to keyword match",
                    src_name, exc,
                )
                # Keyword fallback: conservative — only mark as supporting if clear word overlap
                claim_words = [w.lower() for w in claim.split() if len(w) > 3]
                content_lower = content.lower()
                match_count = sum(1 for w in claim_words if w in content_lower)
                if match_count >= max(1, len(claim_words) // 2):
                    verdict = "supports"
                else:
                    verdict = "not_mentioned"

            if verdict == "supports":
                supported_by.append(src_name)
            elif verdict == "contradicts":
                contradicted_by.append(src_name)
            else:
                not_mentioned_in.append(src_name)

        total_checked = len(supported_by) + len(contradicted_by) + len(not_mentioned_in)
        consensus_score = round(len(supported_by) / total_checked, 2) if total_checked > 0 else 0.0

        return {
            "supported_by": supported_by,
            "contradicted_by": contradicted_by,
            "not_mentioned_in": not_mentioned_in,
            "consensus_score": consensus_score,
        }


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = VerificationAgent()
    agent.run()
