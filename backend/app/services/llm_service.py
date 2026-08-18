"""
LLM Service - Unified interface for language model access.

Supports multiple providers:
- Google Gemini (free tier, immediate access)
- AWS Bedrock / Claude (when access is approved)
- Mock mode (for development without any API key)

The active provider is determined by which API keys are configured in .env.
Priority: Gemini → Bedrock → Mock
"""

import json
from typing import Optional

from app.config import settings


class LLMService:
    """Unified LLM service supporting multiple providers."""

    def __init__(self):
        self._provider = "mock"  # gemini, bedrock, mock
        self._gemini_model = None
        self._bedrock_client = None
        self._available = False

    async def initialize(self):
        """Initialize the best available LLM provider."""

        # Try Gemini first (easiest to set up)
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=settings.gemini_api_key)
                self._gemini_model = genai.GenerativeModel(settings.gemini_model_id)

                # Quick test
                self._provider = "gemini"
                self._available = True
                print(f"   ✓ LLM service initialized (provider: Gemini - {settings.gemini_model_id})")
                return
            except Exception as e:
                print(f"   ⚠ Gemini init failed: {e}")

        # Try Bedrock
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            try:
                import boto3

                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region,
                )
                self._provider = "bedrock"
                self._available = True
                print(f"   ✓ LLM service initialized (provider: Bedrock - {settings.bedrock_model_id})")
                return
            except Exception as e:
                print(f"   ⚠ Bedrock init failed: {e}")

        # Fallback to mock
        self._provider = "mock"
        self._available = True
        print("   ⚠ LLM service: No API keys found - running in MOCK mode")

    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available

    def get_provider(self) -> str:
        """Get the active provider name."""
        return self._provider

    async def invoke_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Invoke the LLM with a prompt.

        Args:
            prompt: The user/task prompt.
            system_prompt: Optional system instructions.
            max_tokens: Maximum tokens in response.
            temperature: Creativity parameter (0-1).

        Returns:
            Model response text.
        """
        if self._provider == "gemini":
            return await self._invoke_gemini(prompt, system_prompt, max_tokens, temperature)
        elif self._provider == "bedrock":
            return await self._invoke_bedrock(prompt, system_prompt, max_tokens, temperature)
        else:
            return await self._mock_response(prompt)

    async def _invoke_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Invoke Google Gemini."""
        try:
            import google.generativeai as genai

            # Build the full prompt with system instructions
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            response = self._gemini_model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )

            return response.text

        except Exception as e:
            print(f"   ✗ Gemini invocation error: {e}")
            return await self._mock_response(prompt)

    async def _invoke_bedrock(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Invoke AWS Bedrock (Claude)."""
        try:
            messages = [{"role": "user", "content": prompt}]

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
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
            print(f"   ✗ Bedrock invocation error: {e}")
            return await self._mock_response(prompt)

    async def _mock_response(self, prompt: str) -> str:
        """Mock response for development."""
        return (
            f"[MOCK LLM RESPONSE] This is a development placeholder. "
            f"Configure GEMINI_API_KEY or AWS credentials in .env for real responses. "
            f"Query received: '{prompt[:100]}...'"
        )


# Singleton instance
llm_service = LLMService()
