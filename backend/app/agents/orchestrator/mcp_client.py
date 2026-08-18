"""
MCP Client Manager for the Orchestrator Agent.

Manages connections to all specialized agent MCP servers and provides
a unified interface for the orchestrator to invoke agent tools.

MCP (Model Context Protocol) is used as the agent communication protocol:
- Each specialized agent runs as an MCP server exposing tools
- The orchestrator acts as an MCP client that invokes these tools
- This provides a standardized, well-defined communication interface

Communication pattern:
  Orchestrator (MCP Client) → Agent MCP Server → Tool Execution → Result
"""

import json
import asyncio
from typing import Optional
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class AgentConnection:
    """Represents a connection to an agent MCP server."""
    name: str
    host: str
    port: int
    status: str = "disconnected"  # connected, disconnected, error
    tools: list[str] = field(default_factory=list)
    _session: Optional[object] = field(default=None, repr=False)


class MCPClientManager:
    """
    Manages MCP client connections to all specialized agent servers.

    In the full implementation, this uses the MCP SDK to connect to
    agent servers via stdio or SSE transport. For development, it provides
    a graceful fallback when agents aren't running.
    """

    def __init__(self):
        # Define all agent connections
        self._agents: dict[str, AgentConnection] = {
            "security_agent": AgentConnection(
                name="security_agent",
                host=settings.mcp_server_host,
                port=settings.mcp_server_base_port,
                tools=["validate_input", "check_rate_limit", "detect_injection"],
            ),
            "nlp_agent": AgentConnection(
                name="nlp_agent",
                host=settings.mcp_server_host,
                port=settings.mcp_server_base_port + 1,
                tools=["process_query", "extract_entities", "expand_query", "summarize_text"],
            ),
            "ir_agent": AgentConnection(
                name="ir_agent",
                host=settings.mcp_server_host,
                port=settings.mcp_server_base_port + 2,
                tools=["retrieve_documents", "search_sources", "index_document"],
            ),
            "analysis_agent": AgentConnection(
                name="analysis_agent",
                host=settings.mcp_server_host,
                port=settings.mcp_server_base_port + 3,
                tools=["analyze_climate_data", "assess_risk", "identify_patterns"],
            ),
            "verification_agent": AgentConnection(
                name="verification_agent",
                host=settings.mcp_server_host,
                port=settings.mcp_server_base_port + 4,
                tools=["verify_claims", "check_source_quality", "cross_reference"],
            ),
            "recommendation_agent": AgentConnection(
                name="recommendation_agent",
                host=settings.mcp_server_host,
                port=settings.mcp_server_base_port + 5,
                tools=["generate_recommendations", "prioritize_actions", "personalize_advice"],
            ),
        }

        self._initialized = False

    async def initialize(self):
        """
        Initialize connections to all agent MCP servers.
        Attempts to connect to each agent and records their status.
        """
        for agent_name, agent in self._agents.items():
            try:
                connected = await self._connect_to_agent(agent)
                agent.status = "connected" if connected else "disconnected"
            except Exception as e:
                agent.status = "error"
                print(f"   ⚠ MCP Client: Failed to connect to {agent_name}: {e}")

        self._initialized = True

    async def _connect_to_agent(self, agent: AgentConnection) -> bool:
        """
        Attempt to connect to an agent's MCP server.

        In production, this establishes a real MCP session using the SDK:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

        For development, we check if the server is reachable.
        """
        try:
            # Attempt a simple TCP connection check
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(agent.host, agent.port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            # Agent server not running - this is expected during development
            return False

    async def call_agent_tool(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict,
    ) -> Optional[dict]:
        """
        Call a tool on a specialized agent via MCP.

        Args:
            agent_name: Name of the target agent.
            tool_name: Name of the tool to invoke.
            arguments: Arguments to pass to the tool.

        Returns:
            Tool result as a dict, or None if agent is unavailable.

        MCP Protocol Flow:
            1. Client sends CallToolRequest with tool_name and arguments
            2. Server processes the request using its specialized logic
            3. Server returns CallToolResult with content
            4. Client parses and returns the result
        """
        agent = self._agents.get(agent_name)

        if not agent:
            print(f"   ✗ MCP Client: Unknown agent '{agent_name}'")
            return None

        if agent.status != "connected":
            # Agent not available - return None so orchestrator can use fallback
            return None

        if tool_name not in agent.tools:
            print(f"   ✗ MCP Client: Tool '{tool_name}' not found on agent '{agent_name}'")
            return None

        try:
            # In production MCP implementation:
            # result = await agent._session.call_tool(tool_name, arguments=arguments)
            # return json.loads(result.content[0].text)

            # For now, send via HTTP to the agent's MCP-compatible endpoint
            result = await self._http_call_agent(agent, tool_name, arguments)
            return result

        except Exception as e:
            print(f"   ✗ MCP Client: Error calling {agent_name}.{tool_name}: {e}")
            return None

    async def _http_call_agent(
        self, agent: AgentConnection, tool_name: str, arguments: dict
    ) -> Optional[dict]:
        """
        HTTP-based fallback for calling agent tools.
        Each agent MCP server also exposes an HTTP endpoint for compatibility.
        """
        import httpx

        url = f"http://{agent.host}:{agent.port}/tools/{tool_name}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=arguments)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(
                        f"   ✗ MCP HTTP: {agent.name}.{tool_name} "
                        f"returned {response.status_code}"
                    )
                    return None
        except (httpx.ConnectError, httpx.TimeoutException):
            # Agent not reachable
            return None
        except Exception as e:
            print(f"   ✗ MCP HTTP error: {e}")
            return None

    async def get_all_agents_status(self) -> dict:
        """Get status of all registered agent connections."""
        # Re-check connectivity
        if not self._initialized:
            await self.initialize()

        statuses = {}
        for name, agent in self._agents.items():
            statuses[name] = {
                "name": agent.name,
                "host": agent.host,
                "port": agent.port,
                "status": agent.status,
                "available_tools": agent.tools,
            }

        return {
            "orchestrator": "active",
            "agents": statuses,
            "total_agents": len(self._agents),
            "connected_agents": sum(
                1 for a in self._agents.values() if a.status == "connected"
            ),
        }

    async def disconnect_all(self):
        """Disconnect from all agent servers."""
        for agent in self._agents.values():
            if agent._session:
                try:
                    # Close MCP session
                    agent._session = None
                except Exception:
                    pass
            agent.status = "disconnected"
