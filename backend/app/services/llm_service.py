"""
LLM Service - AWS Bedrock (primary) with Google Gemini (fallback).

Bedrock (Claude) is preferred for production. When Bedrock credentials are
missing or expired, the service falls back to the configured Gemini API key
so the pipeline keeps full synthesis quality instead of dropping to
extractive fallbacks. If neither provider is reachable the service reports
unavailable and callers use their labelled fallbacks.
"""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Model IDs tried in order when the configured one is rejected.
_GEMINI_CANDIDATES = ("gemini-2.5-flash", "gemini-flash-latest")


class LLMService:
    """LLM service backed by AWS Bedrock with a Gemini fallback."""

    def __init__(self):
        self._bedrock_client = None
        self._available = False
        self._provider = "none"
        self._gemini_model: Optional[str] = None

    async def initialize(self, validate_access: bool = True):
        """
        Initialize the best available provider.

        ``validate_access`` performs a small probe for the main process. Agent
        subprocesses skip that probe because each process would otherwise
        consume an additional model invocation during startup.
        """
        if await self._init_bedrock(validate_access):
            return
        if await self._init_gemini(validate_access):
            return
        self._available = False
        self._provider = "none"
        print("   ✗ LLM service: no provider available "
              "(Bedrock unreachable, Gemini key missing or invalid)")

    async def _init_bedrock(self, validate_access: bool) -> bool:
        if not (settings.aws_access_key_id and settings.aws_secret_access_key):
            return False
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
            if validate_access:
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
            return True
        except Exception as e:
            self._available = False
            print(f"   ✗ LLM service: Bedrock unavailable ({type(e).__name__})")
            return False

    async def _init_gemini(self, validate_access: bool) -> bool:
        key = (settings.gemini_api_key or "").strip()
        if not key:
            return False
        candidates = []
        configured = (settings.gemini_model_id or "").strip()
        if configured:
            candidates.append(configured)
        candidates.extend(m for m in _GEMINI_CANDIDATES if m not in candidates)
        try:
            import httpx

            for model in candidates:
                try:
                    if validate_access:
                        async with httpx.AsyncClient(timeout=20.0) as client:
                            resp = await client.post(
                                "https://generativelanguage.googleapis.com/v1beta/models/"
                                f"{model}:generateContent?key={key}",
                                json={"contents": [{"parts": [{"text": "hi"}]}]},
                            )
                            if resp.status_code != 200:
                                logger.warning(
                                    "Gemini model %s rejected (%s)",
                                    model, resp.status_code,
                                )
                                continue
                    self._gemini_model = model
                    self._provider = "gemini"
                    self._available = True
                    print(f"   ✓ LLM service initialized (provider: Gemini - {model})")
                    return True
                except Exception as exc:
                    logger.warning("Gemini model %s probe failed: %s", model, exc)
        except Exception as exc:
            logger.warning("Gemini init failed: %s", exc)
        return False

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
        """Invoke the active provider; raise if none is available."""
        if not self._available:
            raise RuntimeError("No LLM provider is available")
        if self._provider == "bedrock":
            return await self._invoke_bedrock(prompt, system_prompt, max_tokens, temperature)
        if self._provider == "gemini":
            return await self._invoke_gemini(prompt, system_prompt, max_tokens, temperature)
        raise RuntimeError("No LLM provider is available")

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
                logger.warning("Bedrock error: %s", error_msg)
            raise RuntimeError("AWS Bedrock invocation failed") from e

    async def _invoke_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        import httpx

        key = (settings.gemini_api_key or "").strip()
        text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        # Thinking models spend output budget on internal reasoning, which
        # truncates short answers — disable thinking for direct responses,
        # retrying without the flag if the model rejects it.
        payloads = [
            {"contents": [{"parts": [{"text": text}]}],
             "generationConfig": {"maxOutputTokens": max_tokens,
                                  "temperature": temperature,
                                  "thinkingConfig": {"thinkingBudget": 0}}},
            {"contents": [{"parts": [{"text": text}]}],
             "generationConfig": {"maxOutputTokens": max_tokens,
                                  "temperature": temperature}},
        ]
        last_error: Exception | None = None
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for payload in payloads:
                    try:
                        resp = await client.post(
                            "https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{self._gemini_model}:generateContent?key={key}",
                            json=payload,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    except Exception as e:
                        last_error = e
                        logger.warning("Gemini call failed (%s), retrying", e)
        except Exception as e:
            last_error = last_error or e
        logger.warning("Gemini error: %s", last_error)
        raise RuntimeError("Gemini invocation failed") from last_error


# Singleton instance
llm_service = LLMService()
