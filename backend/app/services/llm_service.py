"""
LLM Service - Claude via AWS Bedrock, with Google Gemini fallback.

Priority order:
  1. AWS Bedrock (Claude) — primary, validated with a live test call on startup
  2. Google Gemini     — free-tier fallback, if GEMINI_API_KEY is set in .env
  3. Mock              — returns structured placeholders when neither is available

To use Gemini while Bedrock credentials are expired:
  - GEMINI_API_KEY is already set in backend/.env (gemini-3.6-flash)
  - The service auto-detects the working model via a probe call on startup

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
        Bedrock is validated with a live probe call so an expired token
        immediately falls through to Gemini instead of silently mocking.
        """
        # --- 1. Try AWS Bedrock (with live validation) ---
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
                # Validate credentials with a minimal test call
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

        # --- 2. Try Google Gemini ---
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=settings.gemini_api_key)
                model_id = settings.gemini_model_id or "gemini-1.5-flash"

                # Probe candidates in order — use the first that responds
                candidates = list(dict.fromkeys([
                    model_id,
                    "gemini-3.6-flash",
                    "gemini-2.0-flash-exp",
                    "gemini-1.5-flash",
                ]))
                chosen = None
                for candidate in candidates:
                    try:
                        m = genai.GenerativeModel(candidate)
                        m.generate_content(
                            "hi",
                            generation_config={"max_output_tokens": 5},
                        )
                        chosen = candidate
                        break
                    except Exception:
                        continue

                if chosen:
                    self._gemini_client = genai.GenerativeModel(chosen)
                    self._provider = "gemini"
                    self._available = True
                    print(f"   ✓ LLM service initialized (provider: Gemini - {chosen})")
                    return
                else:
                    print("   ⚠ LLM service: Gemini key set but no working model found")
            except ImportError:
                print("   ⚠ LLM service: google-generativeai not installed — run: pip install google-generativeai")
            except Exception as e:
                print(f"   ⚠ LLM service: Gemini init failed ({e})")

        # --- 3. Mock fallback ---
        self._provider = "mock"
        self._available = True
        print("   ⚠ LLM service: No working LLM — running in MOCK mode")
        print("      → GEMINI_API_KEY is set; check google-generativeai is installed")

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
        """
        Invoke the best available LLM.

        Args:
            prompt: The user/task prompt.
            system_prompt: Optional system instructions.
            max_tokens: Maximum tokens in response.
            temperature: Creativity parameter (0-1).

        Returns:
            Model response text.
        """
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
        """Call Claude via AWS Bedrock."""
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
                logger.warning("Bedrock invocation error: %s — falling back to Gemini/mock", error_msg)

            # In-request fallback to Gemini if credentials expired mid-session
            if self._gemini_client:
                logger.info("Falling back to Gemini for this request.")
                return await self._invoke_gemini(prompt, system_prompt, max_tokens, temperature)
            return self._mock_response(prompt)

    async def _invoke_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call Google Gemini via the generativeai SDK."""
        try:
            import google.generativeai as genai

            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            response = self._gemini_client.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            return response.text

        except Exception as e:
            logger.warning("Gemini invocation error: %s — falling back to mock", e)
            return self._mock_response(prompt)

    def _mock_response(self, prompt: str) -> str:
        """
        Structured mock so the pipeline produces readable output when no LLM
        is available. Returns valid JSON for prompts that expect JSON.
        """
        prompt_lower = prompt.lower()

        # Analysis agent expects JSON with risk fields
        if '"summary"' in prompt or "risk_level" in prompt_lower or "json object" in prompt_lower:
            return json.dumps({
                "summary": "Live climate data retrieved. Configure GEMINI_API_KEY in backend/.env for AI analysis.",
                "risk_level": "moderate",
                "risk_factors": ["live_data_available"],
                "risk_explanation": "Evidence suggests elevated risk based on retrieved climate data.",
                "detailed_analysis": "Add GEMINI_API_KEY to backend/.env for full AI analysis.",
                "claims": ["Climate data was successfully retrieved from live sources."],
            })

        # Verification agent expects JSON with status field
        if '"status"' in prompt or "fact-check" in prompt_lower or "verdicts" in prompt_lower:
            return json.dumps({
                "status": "partially_supported",
                "confidence": 0.7,
                "explanation": "Mock verification — add GEMINI_API_KEY for real verification.",
                "verdicts": [],
            })

        # Recommendation agent expects JSON with recommendations field
        if "recommendations" in prompt_lower and "json" in prompt_lower:
            return json.dumps({
                "recommendations": [
                    {"action": "Monitor official weather alerts", "priority": "short-term",
                     "explanation": "Stay informed about local conditions.", "category": "awareness"},
                ]
            })

        # Plain text summary
        return (
            "Live climate data retrieved successfully. "
            "Add GEMINI_API_KEY to backend/.env and restart for AI-generated summaries."
        )


# Singleton instance
llm_service = LLMService()
