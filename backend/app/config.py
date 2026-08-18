"""
Application configuration and environment settings.
Loads from .env file and provides typed access to all config values.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "Climora AI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # AWS Bedrock
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"

    # Vector Store (ChromaDB - local)
    vector_store_collection: str = "climora-climate-data"

    # PostgreSQL
    database_url: Optional[str] = "postgresql://postgres:postgres@localhost:5432/climora"

    # Security
    secret_key: str = "change-this-in-production"
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # MCP Configuration
    mcp_server_host: str = "localhost"
    mcp_server_base_port: int = 8100  # Agents will use 8100, 8101, 8102, etc.

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton settings instance
settings = Settings()
