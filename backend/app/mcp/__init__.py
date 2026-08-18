"""
MCP (Model Context Protocol) infrastructure package.

Provides the base MCP server class that all specialized agents inherit from.
Each agent runs as an MCP server exposing tools that the orchestrator can invoke.
"""

from app.mcp.base_agent_server import BaseAgentServer

__all__ = ["BaseAgentServer"]
