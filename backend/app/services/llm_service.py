"""
LLM Service - Claude via AWS Bedrock.

Simple, focused service for invoking Claude through Bedrock.
Supports temporary credentials (session tokens) — just update .env when they expire.

To refresh credentials:
1. Get new AWS keys + session token
2. Update backend/.env with new values
3. Restart the server
"""

import json
from typing import Optional

from app.config import settings


class LLMService:
    """Claude LLM service via AWS Bedrock."""

    def __init__(self):
        self._client = None
        self._available = False
        self._provider = "mock"

    async def initialize(self):
        """Initialize the Bedrock client."""
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            self._provider = "mock"
            self._available = True
            print("   ⚠ LLM service: No AWS credentials - running in MOCK mode")
            return

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

            self._client = boto3.client(**kwargs)
            self._provider = "bedrock"
            self._available = True
            print(f"   ✓ LLM service initialized (provider: Bedrock - {settings.bedrock_model_id})")

        except Exception as e:
            self._provider = "mock"
            self._available = True
            print(f"   ⚠ LLM service: Bedrock init failed ({e}) - running in MOCK mode")

    def is_available(self) -> bool:
        return self._available

    def get_provider(self) -> str:
        return self._provider

    async def invoke_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Invoke Claude via Bedrock.

        Args:
            prompt: The user/task prompt.
            system_prompt: Optional system instructions.
            max_tokens: Maximum tokens in response.
            temperature: Creativity parameter (0-1).

        Returns:
            Model response text.
        """
        if self._provider == "mock":
            return self._mock_response(prompt)

        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            if system_prompt:
                body["system"] = system_prompt

            response = self._client.invoke_model(
                modelId=settings.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            error_msg = str(e)
            print(f"   ✗ Bedrock invocation error: {error_msg}")

            # If token expired, tell the user clearly
            if "ExpiredToken" in error_msg or "expired" in error_msg.lower():
                print("   ⚠ AWS session token has expired! Update .env with new credentials and restart.")

            return self._mock_response(prompt)

    def _mock_response(self, prompt: str) -> str:
        """Mock response when Bedrock isn't available."""
        return (
            f"[MOCK RESPONSE - Bedrock unavailable] "
            f"Update AWS credentials in .env and restart. "
            f"Query: '{prompt[:80]}...'"
        )


# Singleton instance
llm_service = LLMService()
