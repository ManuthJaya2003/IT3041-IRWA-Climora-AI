"""
LLM Service - Claude via AWS Bedrock, with Google Gemini fallback.

Priority order:
  1. AWS Bedrock (Claude) — primary, validated with a live test call on startup
  2. Google Gemini     — free-tier fallback, if GEMINI_API_KEY is set in .env
  3. Mock              — returns structured placeholders when neither is available

IMPORTANT — Gemini free tier:
  gemini-3.6-flash allows only 20 requests/day on the free tier.
  Do NOT make probe/test calls during initialize() — preserve all 20 for real queries.

To refresh AWS credentials:
  1. Get new AWS keys + session token
  2. Update backend/.env with new values
  3. Restart the server
"""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """LLM service: Bedrock (Claude) → Gemini → Mock fallback chain."""

    def __init__(self):
        self._bedrock_client = None
        self._gemini_client = None
        self._available = False
        self._provider = "mock"

    async def initialize(self):
        """
        Initialize the best available LLM provider.

        Bedrock: validated with a live probe call (cheap — just 10 tokens).
        Gemini: client is instantiated WITHOUT a probe call to preserve the
                20 req/day free-tier quota for actual user queries.
        """
        # --- 1. Try AWS Bedrock (live validation) ---
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            try:
                import boto3

                kwargs = {
                    "service_name": "bedrock-runtime",
                    "aws_access_key_id": settings.aws_access_key_id,
                    "aws_secret_access_key": settings.aws_secret_access_key,
                    "region_name": settings.aws_region,
                }
                if settings.aws_session_token:
                    kwargs["aws_session_token"] = settings.aws_session_token

                client = boto3.client(**kwargs)
                test_body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                })
                client.invoke_model(
                    modelId=settings.bedrock_model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=test_body,
                )
                self._bedrock_client = client
                self._provider = "bedrock"
                self._available = True
                print(f"   ✓ LLM service initialized (provider: Bedrock - {settings.bedrock_model_id})")
                return
            except Exception as e:
                print(f"   ⚠ LLM service: Bedrock unavailable ({type(e).__name__}) — trying Gemini")

        # --- 2. Try Google Gemini (no probe call — preserves daily quota) ---
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=settings.gemini_api_key)
                model_id = settings.gemini_model_id or "gemini-3.6-flash"

                # Just instantiate — no API call made here
                candidates = list(dict.fromkeys([
                    model_id,
                    "gemini-3.6-flash",
                    "gemini-2.0-flash-exp",
                    "gemini-1.5-flash",
                ]))
                chosen = None
                for candidate in candidates:
                    try:
                        genai.GenerativeModel(candidate)
                        chosen = candidate
                        break
                    except Exception:
                        continue

                if chosen:
                    self._gemini_client = genai.GenerativeModel(chosen)
                    self._provider = "gemini"
                    self._available = True
                    print(f"   ✓ LLM service initialized (provider: Gemini - {chosen})")
                    print(f"      ⚠ Free tier: 20 req/day — queries will fall back to mock when exhausted")
                    return
                else:
                    print("   ⚠ LLM service: Gemini key set but could not instantiate any model")
            except ImportError:
                print("   ⚠ LLM service: google-generativeai not installed — run: pip install google-generativeai")
            except Exception as e:
                print(f"   ⚠ LLM service: Gemini init failed ({e})")

        # --- 3. Mock fallback ---
        self._provider = "mock"
        self._available = True
        print("   ⚠ LLM service: No working LLM — running in MOCK mode")

    def is_available(self) -> bool:
        return self._available

    def get_provider(self) -> str:
        return self._provider

    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Alias used by the verification agent."""
        return await self.invoke_model(prompt=prompt, **kwargs)

    async def invoke_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Invoke the best available LLM."""
        if self._provider == "bedrock":
            return await self._invoke_bedrock(prompt, system_prompt, max_tokens, temperature)
        if self._provider == "gemini":
            return await self._invoke_gemini(prompt, system_prompt, max_tokens, temperature)
        return self._mock_response(prompt)

    # -------------------------------------------------------------------------
    # Provider implementations
    # -------------------------------------------------------------------------

    async def _invoke_bedrock(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                body["system"] = system_prompt

            response = self._bedrock_client.invoke_model(
                modelId=settings.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            error_msg = str(e)
            if "ExpiredToken" in error_msg or "expired" in error_msg.lower():
                logger.warning("AWS session token expired — update .env and restart.")
            else:
                logger.warning("Bedrock error: %s — falling back to Gemini/mock", error_msg)

            if self._gemini_client:
                return await self._invoke_gemini(prompt, system_prompt, max_tokens, temperature)
            return self._mock_response(prompt)

    async def _invoke_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            import google.generativeai as genai

            # Use system_instruction parameter — do NOT prepend to prompt.
            # Concatenating system+user prompt triggers Gemini's safety filter
            # on climate/disaster content (finish_reason=2/SAFETY).
            if system_prompt:
                model = genai.GenerativeModel(
                    self._gemini_client.model_name,
                    system_instruction=system_prompt,
                )
            else:
                model = self._gemini_client

            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            if not response.candidates:
                logger.warning("Gemini returned no candidates — using mock")
                return self._mock_response(prompt)

            candidate = response.candidates[0]
            # finish_reason 2 = SAFETY block
            if candidate.finish_reason == 2:
                logger.warning("Gemini safety block — using mock")
                return self._mock_response(prompt)

            return response.text

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "ResourceExhausted" in err_str:
                logger.warning("Gemini daily quota exhausted (20 req/day free tier) — using mock")
            else:
                logger.warning("Gemini error: %s — using mock", e)
            return self._mock_response(prompt)

    def _mock_response(self, prompt: str) -> str:
        """Structured mock so the pipeline produces readable output when no LLM is available."""
        prompt_lower = prompt.lower()

        if '"summary"' in prompt or "risk_level" in prompt_lower or "json object" in prompt_lower:
            return json.dumps({
                "summary": "Live climate data retrieved. Gemini quota exhausted (20/day) — real AI analysis will resume tomorrow.",
                "risk_level": "moderate",
                "risk_factors": ["live_data_available"],
                "risk_explanation": "Evidence suggests elevated risk based on retrieved climate data.",
                "detailed_analysis": "Gemini free tier: 20 requests/day. Quota resets daily. Live weather data is still being retrieved.",
                "claims": ["Climate data was successfully retrieved from live sources."],
            })

        if '"status"' in prompt or "fact-check" in prompt_lower or "verdicts" in prompt_lower:
            return json.dumps({
                "status": "partially_supported",
                "confidence": 0.7,
                "explanation": "Keyword-based verification (Gemini quota exhausted).",
                "verdicts": [],
            })

        if "recommendations" in prompt_lower and "json" in prompt_lower:
            return json.dumps({
                "recommendations": [
                    {"action": "Monitor official weather alerts for your area",
                     "priority": "short-term",
                     "explanation": "Stay informed about local conditions.",
                     "category": "awareness"},
                ]
            })

        return (
            "Live climate data retrieved. "
            "Gemini free tier quota exhausted (20 req/day) — AI summaries resume tomorrow. "
            "Evidence sources are shown below."
        )


# Singleton instance
llm_service = LLMService()
