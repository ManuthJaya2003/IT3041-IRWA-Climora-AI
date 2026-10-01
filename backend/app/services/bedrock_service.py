"""
AWS Bedrock LLM Service.
Provides access to foundation models (Claude, etc.) via Amazon Bedrock.
Includes a fallback mock mode for development when Bedrock access is pending.
"""

import json
from typing import Optional

from app.config import settings


class BedrockService:
    """Service for interacting with AWS Bedrock foundation models."""

    def __init__(self):
        self._client = None
        self._available = False
        self._mock_mode = False

    async def initialize(self):
        """Initialize the Bedrock client."""
        try:
            import boto3

            if settings.aws_access_key_id and settings.aws_secret_access_key:
                self._client = boto3.client(
                    "bedrock-runtime",
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region,
                )
                self._available = True
                print("   ✓ Bedrock service initialized")
            else:
                self._mock_mode = True
                self._available = True
                print("   ⚠ Bedrock: No AWS credentials found - running in MOCK mode")

        except ImportError:
            self._mock_mode = True
            self._available = True
            print("   ⚠ Bedrock: boto3 not installed - running in MOCK mode")
        except Exception as e:
            self._mock_mode = True
            self._available = True
            print(f"   ⚠ Bedrock: Init failed ({e}) - running in MOCK mode")

    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available

    async def invoke_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Invoke the foundation model with a prompt.

        Args:
            prompt: The user/task prompt.
            system_prompt: Optional system instructions.
            max_tokens: Maximum tokens in response.
            temperature: Creativity parameter (0-1).

        Returns:
            Model response text.
        """
        if self._mock_mode:
            return await self._mock_response(prompt, system_prompt)

        try:
            # Claude model via Bedrock Messages API
            messages = [{"role": "user", "content": prompt}]

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
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
            print(f"   ✗ Bedrock invocation error: {e}")
            # Fallback to mock if real call fails
            return await self._mock_response(prompt, system_prompt)

    async def _mock_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate a mock response for development/testing.
        This allows the pipeline to work end-to-end without Bedrock access.
        """
        return (
            f"[MOCK LLM RESPONSE] This is a development placeholder. "
            f"In production, this would be processed by {settings.bedrock_model_id}. "
            f"Query received: '{prompt[:100]}...'"
        )


# Singleton instance
bedrock_service = BedrockService()
