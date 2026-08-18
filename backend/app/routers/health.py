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
