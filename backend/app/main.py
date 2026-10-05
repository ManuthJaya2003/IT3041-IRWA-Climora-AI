"""
Climora AI - FastAPI Application Entry Point

Agentic AI-Powered Climate Intelligence & Decision Support System
"""

import multiprocessing
import logging

# Required on Windows: prevents subprocesses from re-executing this module
# when multiprocessing uses the 'spawn' start method (Windows default).
multiprocessing.freeze_support()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import alerts, chat, health, agents, vector_store, speech, billing


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
logger = logging.getLogger(__name__)


def _validate_production_security() -> None:
    """Reject unsafe settings before a production instance accepts traffic."""
    if settings.environment.lower() not in {"production", "prod"}:
        return

    if (
        settings.debug
        or settings.secret_key == "replace-with-a-random-production-secret"
        or len(settings.secret_key) < 32
    ):
        raise RuntimeError(
            "Production requires DEBUG=false and a SECRET_KEY of at least 32 characters."
        )
    if not settings.admin_token or len(settings.admin_token) < 32:
        raise RuntimeError(
            "Production requires an ADMIN_TOKEN of at least 32 characters."
        )
    if not settings.cors_origins or any(
        origin == "*" or not origin.lower().startswith("https://")
        for origin in settings.cors_origins
    ):
        raise RuntimeError(
            "Production CORS_ORIGINS must contain only explicit HTTPS origins."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    _validate_production_security()
    print(f"🌍 Starting {settings.app_name} v{settings.app_version}")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")

    if settings.secret_key == "replace-with-a-random-production-secret":
        print("   ⚠ WARNING: SECRET_KEY is the default value — set a real one in production.")
    if not settings.admin_token:
        print("   ⚠ WARNING: ADMIN_TOKEN is not set — protected vector endpoints are open (dev mode).")

    # Initialize services on startup — each independently, so one failure
    # (e.g. no cloud credentials) degrades gracefully instead of aborting startup.
    from app.services.llm_service import llm_service
    from app.services.embedding_service import embedding_service
    from app.services.vector_store_service import vector_store_service
    from app.services.tts_service import tts_service
    from app.services.history_service import history_service
    from app.services.alert_service import alert_service
    import asyncio as _alert_asyncio

    for svc_name, svc in [
        ("llm", llm_service),
        ("embedding", embedding_service),
        ("vector store", vector_store_service),
        ("tts", tts_service),
        ("chat history", history_service),
        ("alert service", alert_service),
    ]:
        try:
            await svc.initialize()
            print(f"   ✓ {svc_name} service ready")
        except Exception as exc:
            print(f"   ⚠ {svc_name} service failed to initialize ({exc}) — continuing with fallbacks")

    alert_task = None
    if settings.vapid_public_key and settings.vapid_private_key:
        async def monitor_alerts():
            while True:
                try:
                    await alert_service.monitor_once()
                except Exception:
                    logger.exception("Weather alert monitor cycle failed")
                await _alert_asyncio.sleep(max(60, settings.alert_poll_interval_seconds))
        alert_task = _alert_asyncio.create_task(monitor_alerts())
        print(f"   ✓ Weather alert monitor enabled (every {settings.alert_poll_interval_seconds}s)")

    print("   Services initialized (see warnings above for any degraded service)")

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

    # Report which agents actually survived startup — anything missing is
    # covered by orchestrator fallbacks, but the operator should know.
    alive = [p for p in _agent_processes if p.is_alive()]
    dead = [p.name for p in _agent_processes if not p.is_alive()]
    if dead:
        print(f"   ⚠ {len(dead)} agent(s) failed to start and will use fallbacks: {', '.join(dead)}")
    print(f"   ✓ Agents ready ({len(alive)}/{len(_agent_processes)} running)")

    yield

    if alert_task:
        alert_task.cancel()

    # Shutdown — terminate agent subprocesses cleanly
    print(f"🛑 Shutting down {settings.app_name}")
    if alert_task is not None:
        alert_task.cancel()
        try:
            await alert_task
        except _alert_asyncio.CancelledError:
            pass
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
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "description": "Agentic AI-Powered Climate Intelligence & Decision Support System",
    }
