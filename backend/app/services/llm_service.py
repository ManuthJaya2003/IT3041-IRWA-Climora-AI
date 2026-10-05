"""
LLM Service - Claude via AWS Bedrock only.

There are no alternate provider or mock fallbacks. A Bedrock failure is surfaced
to the caller so the application cannot silently answer with another model.

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
    """LLM service backed exclusively by AWS Bedrock."""

    def __init__(self):
        self._bedrock_client = None
        self._available = False
        self._provider = "bedrock"

    async def initialize(self):
        """
        Initialize and validate the Bedrock provider.
        """
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
                self._available = False
                print(f"   ✗ LLM service: Bedrock unavailable ({type(e).__name__})")
                return

        self._available = False
        print("   ✗ LLM service: AWS Bedrock credentials are not configured")

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
        """Invoke AWS Bedrock; fail explicitly if it is unavailable."""
        if self._provider != "bedrock" or not self._available or self._bedrock_client is None:
            raise RuntimeError("AWS Bedrock is unavailable; no alternate AI provider is permitted")
        return await self._invoke_bedrock(prompt, system_prompt, max_tokens, temperature)

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


# Singleton instance
llm_service = LLMService()
