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
                "owner": "Member 1",
                "port": 8000,
            },
            {
                "name": "Security Agent",
                "role": "Input validation, threat detection, access control",
                "status": "active",
                "owner": "Member 2",
                "port": 8100,
            },
            {
                "name": "NLP Agent",
                "role": "Intent detection, entity extraction, query expansion",
                "status": "active",
                "owner": "Member 2",
                "port": 8101,
            },
            {
                "name": "Information Retrieval Agent",
                "role": "Searches sources, retrieves documents, returns evidence",
                "status": "active",
                "owner": "Member 3",
                "port": 8102,
            },
            {
                "name": "Climate Analysis Agent",
                "role": "Analyzes evidence, identifies patterns, estimates risk",
                "status": "active",
                "owner": "Member 4",
                "port": 8103,
            },
            {
                "name": "Verification Agent",
                "role": "Checks source quality, consistency, evidence support",
                "status": "active",
                "owner": "Member 3",
                "port": 8104,
            },
            {
                "name": "Recommendation Agent",
                "role": "Converts analysis into practical recommendations",
                "status": "active",
                "owner": "Member 4",
                "port": 8105,
            },
        ]
    }
