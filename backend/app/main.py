"""
Climora AI - FastAPI Application Entry Point

Agentic AI-Powered Climate Intelligence & Decision Support System
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, health, agents, vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    print(f"🌍 Starting {settings.app_name} v{settings.app_version}")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")

    # Initialize services on startup
    from app.services.llm_service import llm_service
    from app.services.embedding_service import embedding_service
    from app.services.vector_store_service import vector_store_service

    await llm_service.initialize()
    await embedding_service.initialize()
    await vector_store_service.initialize()

    print("   Services initialized successfully")

    yield

    # Shutdown
    print(f"🛑 Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    description="Agentic AI-Powered Climate Intelligence & Decision Support System",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(vector_store.router, prefix="/api/v1/vectors", tags=["Vector Store"])


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "description": "Agentic AI-Powered Climate Intelligence & Decision Support System",
    }
