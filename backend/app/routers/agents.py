"""Agent management and status endpoints."""

from fastapi import APIRouter

from app.agents.orchestrator.orchestrator_agent import OrchestratorAgent

router = APIRouter()

orchestrator = OrchestratorAgent()


@router.get("/status")
async def get_agents_status():
    """Get the status of all registered agents."""
    return await orchestrator.get_agents_status()


@router.get("/list")
async def list_agents():
    """List all available agents and their capabilities."""
    return {
        "agents": [
            {
                "name": "Orchestrator Agent",
                "role": "Coordinates all agents and manages workflow",
                "status": "active",
                "owner": "orchestrator",
            },
            {
                "name": "NLP Agent",
                "role": "Intent detection, entity extraction, query expansion",
                "status": "stub",
                "owner": "teammate",
            },
            {
                "name": "Information Retrieval Agent",
                "role": "Searches sources, retrieves documents, returns evidence",
                "status": "stub",
                "owner": "teammate",
            },
            {
                "name": "Climate Analysis Agent",
                "role": "Analyzes evidence, identifies patterns, estimates risk",
                "status": "stub",
                "owner": "teammate",
            },
            {
                "name": "Verification Agent",
                "role": "Checks source quality, consistency, evidence support",
                "status": "stub",
                "owner": "teammate",
            },
            {
                "name": "Recommendation Agent",
                "role": "Converts analysis into practical recommendations",
                "status": "stub",
                "owner": "teammate",
            },
            {
                "name": "Security Agent",
                "role": "Input validation, threat detection, access control",
                "status": "stub",
                "owner": "teammate",
            },
        ]
    }
