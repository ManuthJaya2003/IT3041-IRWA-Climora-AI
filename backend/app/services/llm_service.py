"""
LLM Service - AWS Bedrock (primary) with Google Gemini (fallback).

Bedrock (Claude) is preferred for production. When Bedrock credentials are
missing or expired, the service falls back to the configured Gemini API key
so the pipeline keeps full synthesis quality instead of dropping to
extractive fallbacks. Calls fail over between providers automatically, so
agent subprocesses (which skip the paid Bedrock probe at startup) still end
up on a working provider instead of failing every call.
"""

import asyncio
import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Stable models first: versioned preview aliases 503 under free-tier load.
_GEMINI_CANDIDATES = ("gemini-2.5-flash", "gemini-flash-latest")


class LLMService:
    """LLM service with automatic Bedrock <-> Gemini failover."""

    def __init__(self):
        self._bedrock_client = None
        self._bedrock_usable = False
        self._gemini_model: Optional[str] = None
        self._gemini_usable = False
        self._available = False
        self._provider = "none"

    async def initialize(self, validate_access: bool = True):
        """
        Detect working providers.

        ``validate_access`` performs paid Bedrock probe for the main process.
        Agent subprocesses skip it (each probe would cost a model invocation)
        and rely on free Gemini probing plus runtime failover.
        """
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            if validate_access:
                self._bedrock_usable = await self._probe_bedrock()
            else:
                # Unverified: kept as a candidate; the first failed call
                # drops it and fails over to Gemini automatically.
                self._bedrock_usable = True
        await self._init_gemini(probe=validate_access)
        self._refresh_state(log=True)

    def _refresh_state(self, log: bool = False):
        self._available = self._bedrock_usable or self._gemini_usable
        if self._bedrock_usable:
            self._provider = "bedrock"
        elif self._gemini_usable:
            self._provider = "gemini"
        else:
            self._provider = "none"
        if log:
            if self._bedrock_usable:
                print("   ✓ LLM service: Bedrock available", end="")
                print("; Gemini fallback ready"
                      if self._gemini_usable else " (no Gemini fallback)")
            elif self._gemini_usable:
                print(f"   ✓ LLM service initialized (provider: Gemini - {self._gemini_model})")
            else:
                print("   ✗ LLM service: no provider available "
                      "(Bedrock unreachable, Gemini key missing or invalid)")

    async def _probe_bedrock(self) -> bool:
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
            return True
        except Exception as e:
            print(f"   ✗ LLM service: Bedrock unavailable ({type(e).__name__})")
            return False

    def _bedrock_client_lazy(self):
        if self._bedrock_client is None:
            import boto3

            kwargs = {
                "service_name": "bedrock-runtime",
                "aws_access_key_id": settings.aws_access_key_id,
                "aws_secret_access_key": settings.aws_secret_access_key,
                "region_name": settings.aws_region,
            }
            if settings.aws_session_token:
                kwargs["aws_session_token"] = settings.aws_session_token
            self._bedrock_client = boto3.client(**kwargs)
        return self._bedrock_client

    async def _init_gemini(self, probe: bool) -> bool:
        key = (settings.gemini_api_key or "").strip()
        if not key:
            return False
        candidates = [m for m in _GEMINI_CANDIDATES]
        configured = (settings.gemini_model_id or "").strip()
        if configured and configured not in candidates:
            candidates.append(configured)
        if not probe:
            self._gemini_model = candidates[0]
            self._gemini_usable = True
            return True
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20.0) as client:
                for model in candidates:
                    try:
                        resp = await client.post(
                            "https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{model}:generateContent?key={key}",
                            json={"contents": [{"parts": [{"text": "hi"}]}]},
                        )
                        if resp.status_code != 200:
                            logger.warning("Gemini model %s rejected (%s)",
                                           model, resp.status_code)
                            continue
                        self._gemini_model = model
                        self._gemini_usable = True
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
        """Invoke providers in order, failing over automatically."""
        errors = []
        if self._bedrock_usable:
            try:
                return await self._invoke_bedrock(prompt, system_prompt,
                                                  max_tokens, temperature)
            except Exception as e:
                errors.append(f"bedrock: {e}")
                self._bedrock_usable = False
                self._refresh_state()
        if self._gemini_usable:
            try:
                return await self._invoke_gemini(prompt, system_prompt,
                                                 max_tokens, temperature)
            except Exception as e:
                errors.append(f"gemini: {e}")
                self._gemini_usable = False
                self._refresh_state()
        raise RuntimeError("No LLM provider is available ("
                           + "; ".join(errors) + ")")

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
            client = self._bedrock_client_lazy()
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                body["system"] = system_prompt

            response = await asyncio.to_thread(
                client.invoke_model,
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
        models = [self._gemini_model or _GEMINI_CANDIDATES[0]]
        models.extend(m for m in _GEMINI_CANDIDATES if m not in models)
        last_error: Exception | None = None
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for model in models:
                    use_thinking = True
                    for attempt in range(3):
                        config = {"maxOutputTokens": max_tokens,
                                  "temperature": temperature}
                        if use_thinking:
                            config["thinkingConfig"] = {"thinkingBudget": 0}
                        try:
                            resp = await client.post(
                                "https://generativelanguage.googleapis.com"
                                "/v1beta/models/"
                                f"{model}:generateContent?key={key}",
                                json={"contents": [{"parts": [{"text": text}]}],
                                      "generationConfig": config},
                            )
                            if resp.status_code in (503, 429):
                                last_error = RuntimeError(
                                    f"Gemini {model} overloaded ({resp.status_code})")
                                await asyncio.sleep(2 ** attempt)
                                continue
                            if resp.status_code == 400 and use_thinking:
                                use_thinking = False
                                continue
                            resp.raise_for_status()
                            data = resp.json()
                            self._gemini_model = model
                            return (data["candidates"][0]["content"]
                                    ["parts"][0]["text"])
                        except Exception as e:
                            last_error = e
                            logger.warning("Gemini call failed (%s)", e)
                            break
        except Exception as e:
            last_error = last_error or e
        logger.warning("Gemini error: %s", last_error)
        raise RuntimeError("Gemini invocation failed") from last_error


# Singleton instance
llm_service = LLMService()
