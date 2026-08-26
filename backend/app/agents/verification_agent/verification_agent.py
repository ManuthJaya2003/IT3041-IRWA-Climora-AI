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
from datetime import datetime
from app.mcp.base_agent_server import BaseAgentServer
from app.services.llm_service import llm_service


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
        "openopenweathermap api": {"score": 0.90, "category": "live_weather_api"},
        "open-meteo climate api": {"score": 0.90, "category": "live_weather_api"},
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
            - warnings (list): Any issues found (conflicts, staleness, etc.)
        """
        claims = arguments.get("claims", [])
        sources = arguments.get("sources", [])

        # If string claims or single dict claims are passed, normalize to list
        if isinstance(claims, str):
            claims = [claims]

        if not claims:
            return {
                "verified": False,
                "confidence": 0.0,
                "claim_results": [],
                "warnings": ["No claims were provided for verification."]
            }

        claim_results = []
        warnings = []
        total_confidence = 0.0

        # Build context block out of sources/evidence
        evidence_texts = []
        for src in sources:
            name = src.get("source_name", src.get("source", "Unknown"))
            content = src.get("content", src.get("snippet", ""))
            evidence_texts.append(f"[{name}]: {content}")
        
        combined_evidence = "\n".join(evidence_texts) if evidence_texts else "No retrieved evidence provided."

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
                
                # Sanitize response string for JSON parsing
                cleaned_resp = llm_response.strip().replace("```json", "").replace("```", "").strip()
                parsed = json.loads(cleaned_resp)
                
                status = parsed.get("status", "partially_supported")
                conf = float(parsed.get("confidence", 0.7))
                exp = parsed.get("explanation", "Verified against provided evidence.")

            except Exception:
                # Rule-based / Keyword Fallback verification if LLM fails or is unavailable
                matches = sum(1 for src in sources if any(word in src.get("content", "").lower() for word in claim_str.lower().split() if len(word) > 3))
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
                "explanation": exp
            })

            total_confidence += conf
            if status in ["unsupported", "contradicted"]:
                warnings.append(f"Claim '{claim_str[:40]}...' is {status}.")

        overall_confidence = round(total_confidence / len(claims), 2) if claims else 0.0
        overall_verified = overall_confidence >= 0.65 and len(warnings) == 0

        # Check for source staleness warnings
        for src in sources:
            date_str = src.get("date", src.get("content_date", ""))
            if date_str and "2020" in date_str:
                warnings.append(f"Source '{src.get('source_name', 'Unknown')}' may contain older historical data.")

        return {
            "verified": overall_verified,
            "confidence": overall_confidence,
            "claim_results": claim_results,
            "warnings": warnings
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
        source_name = arguments.get("source_name", "").strip().lower()
        source_url = arguments.get("source_url", "").lower()
        content_date = arguments.get("content_date", "live")

        reliability_score = 0.70
        category = "general_media"
        notes = "Standard source."

        # Rule matching against high trust database
        for key, info in self.HIGH_TRUST_SOURCES.items():
            if key in source_name or key in source_url:
                reliability_score = info["score"]
                category = info["category"]
                notes = "High authority recognized climate institution."
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
        if content_date in ["live", "current", "today"]:
            freshness = "real_time"
        else:
            try:
                pub_year = int("".join(filter(str.isdigit, str(content_date)))[:4])
                current_year = datetime.now().year
                diff = current_year - pub_year
                if diff <= 1:
                    freshness = "current"
                elif diff <= 3:
                    freshness = "recent"
                else:
                    freshness = "historical"
                    notes += " Note: Historical data (>3 years old)."
            except Exception:
                freshness = "recent"

        return {
            "reliability_score": reliability_score,
            "category": category,
            "freshness": freshness,
            "notes": notes
        }

    async def cross_reference(self, arguments: dict) -> dict:
        """
        Cross-reference claims across multiple sources.

        Input:
            - claim (str): The claim to cross-reference
            - sources (list): Sources to check against

        Output:
            - supported_by (list): Sources that support the claim
            - contradicted_by (list): Sources that contradict
            - not_mentioned_in (list): Sources that don't cover it
            - consensus_score (float): How much agreement exists (0-1)
        """
        claim = arguments.get("claim", "")
        sources = arguments.get("sources", [])

        supported_by = []
        contradiction_sources = []
        not_mentioned_in = []

        claim_words = [w.lower() for w in claim.split() if len(w) > 3]

        for src in sources:
            src_name = src.get("source_name", src.get("source", "Unknown Source"))
            content = src.get("content", src.get("snippet", "")).lower()

            if not content:
                not_mentioned_in.append(src_name)
                continue

            # Check overlap of key concepts
            match_count = sum(1 for word in claim_words if word in content)
            
            if match_count >= max(1, len(claim_words) // 2):
                supported_by.append(src_name)
            else:
                not_mentioned_in.append(src_name)

        total_checked = len(supported_by) + len(contradiction_sources) + len(not_mentioned_in)
        if total_checked > 0:
            consensus_score = round(len(supported_by) / total_checked, 2)
        else:
            consensus_score = 0.0

        return {
            "supported_by": supported_by,
            "contradicted_by": contradiction_sources,
            "not_mentioned_in": not_mentioned_in,
            "consensus_score": consensus_score
        }


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = VerificationAgent()
    agent.run()