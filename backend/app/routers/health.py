"""Health check endpoints."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with service status."""
    from app.services.llm_service import llm_service
    from app.services.vector_store_service import vector_store_service

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "services": {
            "llm": {"available": llm_service.is_available(), "provider": llm_service.get_provider()},
            "vector_store": vector_store_service.is_available(),
        },
        "environment": settings.environment,
    }


@router.get("/health/bedrock-models")
async def list_bedrock_models():
    """List available Bedrock models (requires valid AWS credentials)."""
    from app.config import settings

    try:
        import boto3

        boto3_kwargs = {
            "service_name": "bedrock",
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
            "region_name": settings.aws_region,
        }
        if settings.aws_session_token:
            boto3_kwargs["aws_session_token"] = settings.aws_session_token

        client = boto3.client(**boto3_kwargs)
        response = client.list_foundation_models()

        models = [
            {
                "model_id": m["modelId"],
                "model_name": m.get("modelName", ""),
                "provider": m.get("providerName", ""),
            }
            for m in response.get("modelSummaries", [])
            if "anthropic" in m.get("providerName", "").lower()
            or "claude" in m.get("modelId", "").lower()
        ]

        return {"available_claude_models": models, "total": len(models)}

    except Exception as e:
        return {"error": str(e)}
