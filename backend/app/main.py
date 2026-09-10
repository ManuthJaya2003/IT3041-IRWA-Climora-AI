"""
Climora AI - FastAPI Application Entry Point

Agentic AI-Powered Climate Intelligence & Decision Support System
"""

import multiprocessing

# Required on Windows: prevents subprocesses from re-executing this module
# when multiprocessing uses the 'spawn' start method (Windows default).
multiprocessing.freeze_support()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, health, agents, vector_store


def _run_ir_agent():
    """Entry point for IR Agent subprocess."""
    from app.agents.ir_agent.ir_agent import IRAgent
    IRAgent().run()


def _run_verification_agent():
    """Entry point for Verification Agent subprocess."""
    from app.agents.verification_agent.verification_agent import VerificationAgent
    VerificationAgent().run()


# Keep references so we can terminate on shutdown
_agent_processes: list[multiprocessing.Process] = []


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

    # Auto-start IR and Verification agents as background subprocesses.
    # This means you only need one terminal: `uvicorn app.main:app`
    for name, target in [
        ("ir_agent      (port 8102)", _run_ir_agent),
        ("verification  (port 8104)", _run_verification_agent),
    ]:
        proc = multiprocessing.Process(target=target, name=name, daemon=True)
        proc.start()
        _agent_processes.append(proc)
        print(f"   🤖 Started {name}  [pid {proc.pid}]")

    yield

    # Shutdown — terminate agent subprocesses cleanly
    print(f"🛑 Shutting down {settings.app_name}")
    for proc in _agent_processes:
        proc.terminate()
        proc.join(timeout=3)
        print(f"   ✓ {proc.name} stopped")


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
