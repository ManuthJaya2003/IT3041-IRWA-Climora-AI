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
from app.routers import chat, health, agents, vector_store, speech


def _run_security_agent():
    """Entry point for Security Agent subprocess."""
    from app.agents.security_agent.security_agent import SecurityAgent
    SecurityAgent().run()


def _run_nlp_agent():
    """Entry point for NLP Agent subprocess."""
    from app.agents.nlp_agent.nlp_agent import NLPAgent
    NLPAgent().run()


def _run_ir_agent():
    """Entry point for IR Agent subprocess."""
    from app.agents.ir_agent.ir_agent import IRAgent
    IRAgent().run()


def _run_analysis_agent():
    """Entry point for Analysis Agent subprocess."""
    from app.agents.analysis_agent.analysis_agent import AnalysisAgent
    AnalysisAgent().run()


def _run_verification_agent():
    """Entry point for Verification Agent subprocess."""
    from app.agents.verification_agent.verification_agent import VerificationAgent
    VerificationAgent().run()


def _run_recommendation_agent():
    """Entry point for Recommendation Agent subprocess."""
    from app.agents.recommendation_agent.recommendation_agent import RecommendationAgent
    RecommendationAgent().run()


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
    from app.services.tts_service import tts_service

    await llm_service.initialize()
    await embedding_service.initialize()
    await vector_store_service.initialize()
    await tts_service.initialize()

    print("   Services initialized successfully")

    # Auto-start all 6 agents as daemon subprocesses — only one terminal needed.
    for name, target in [
        ("security_agent       (port 8100)", _run_security_agent),
        ("nlp_agent            (port 8101)", _run_nlp_agent),
        ("ir_agent             (port 8102)", _run_ir_agent),
        ("analysis_agent       (port 8103)", _run_analysis_agent),
        ("verification_agent   (port 8104)", _run_verification_agent),
        ("recommendation_agent (port 8105)", _run_recommendation_agent),
    ]:
        proc = multiprocessing.Process(target=target, name=name, daemon=True)
        proc.start()
        _agent_processes.append(proc)
        print(f"   🤖 Started {name}  [pid {proc.pid}]")

    # Give agents a moment to bind their ports before the first request arrives.
    # Without this delay the MCP client's initial TCP probe finds all ports closed
    # and marks every agent as disconnected, forcing fallback for the first query.
    import asyncio as _asyncio
    await _asyncio.sleep(3)
    print("   ✓ Agents ready")

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
app.include_router(speech.router, prefix="/api/v1/speech", tags=["Speech"])


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "description": "Agentic AI-Powered Climate Intelligence & Decision Support System",
    }
