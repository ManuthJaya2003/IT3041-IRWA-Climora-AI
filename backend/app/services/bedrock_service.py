"""
AWS Bedrock LLM Service.
Provides access to foundation models (Claude, etc.) via Amazon Bedrock.
"""

import json
from typing import Optional

from app.config import settings


class BedrockService:
    """Service for interacting with AWS Bedrock foundation models."""

    def __init__(self):
        self._client = None
        self._available = False

    async def initialize(self):
        """Initialize the Bedrock client."""
        try:
            import boto3

            if settings.aws_access_key_id and settings.aws_secret_access_key:
                client_kwargs = {
                    "service_name": "bedrock-runtime",
                    "aws_access_key_id": settings.aws_access_key_id,
                    "aws_secret_access_key": settings.aws_secret_access_key,
                    "region_name": settings.aws_region,
                }
                if settings.aws_session_token:
                    client_kwargs["aws_session_token"] = settings.aws_session_token
                self._client = boto3.client(**client_kwargs)
                self._available = True
                print("   ✓ Bedrock service initialized")
            else:
                print("   ✗ Bedrock: No AWS credentials found")

        except ImportError:
            print("   ✗ Bedrock: boto3 is not installed")
        except Exception as e:
            print(f"   ✗ Bedrock: Init failed ({type(e).__name__})")

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
            print(f"   ✗ Bedrock invocation error: {type(e).__name__}")
            raise RuntimeError("AWS Bedrock invocation failed") from e


# Singleton instance
bedrock_service = BedrockService()
