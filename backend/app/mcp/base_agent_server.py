"""
Base MCP Agent Server.

All specialized agents inherit from this base class. It provides:
- MCP server setup with tool registration
- HTTP fallback server (FastAPI-based) for development
- Standard lifecycle management (start, stop, health check)
- Logging and error handling

Usage:
    class MyAgent(BaseAgentServer):
        def __init__(self):
            super().__init__(name="my_agent", port=8101)
            self.register_tool("my_tool", self.my_tool_handler, "Description of my tool")

        async def my_tool_handler(self, arguments: dict) -> dict:
            # Your agent logic here
            return {"result": "processed"}
"""

import asyncio
import uvicorn
from typing import Callable, Optional
from dataclasses import dataclass, field
from fastapi import FastAPI
from pydantic import BaseModel


@dataclass
class ToolDefinition:
    """Definition of a tool exposed by an agent."""
    name: str
    handler: Callable
    description: str
    input_schema: Optional[dict] = None


class BaseAgentServer:
    """
    Base class for all Climora AI agent MCP servers.

    Each agent:
    1. Inherits from this class
    2. Registers its tools in __init__
    3. Implements handler methods for each tool
    4. Can be started as a standalone server

    The server exposes tools via both:
    - MCP protocol (for production agent-to-agent communication)
    - HTTP REST endpoints (for development/testing)
    """

    def __init__(self, name: str, port: int, description: str = ""):
        self.name = name
        self.port = port
        self.description = description
        self._tools: dict[str, ToolDefinition] = {}
        self._running = False

        # Create the HTTP server for development/fallback
        self._app = FastAPI(
            title=f"Climora AI - {name}",
            description=description or f"MCP Server for {name}",
        )
        self._setup_routes()

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str,
        input_schema: Optional[dict] = None,
    ):
        """
        Register a tool that this agent exposes.

        Args:
            name: Tool name (must match what orchestrator expects).
            handler: Async function that processes the tool call.
            description: Human-readable description of what the tool does.
            input_schema: Optional JSON schema for the tool's input.
        """
        self._tools[name] = ToolDefinition(
            name=name,
            handler=handler,
            description=description,
            input_schema=input_schema,
        )

    def _setup_routes(self):
        """Set up HTTP routes that mirror MCP tool calls."""

        @self._app.get("/health")
        async def health():
            return {
                "agent": self.name,
                "status": "running" if self._running else "starting",
                "tools": list(self._tools.keys()),
            }

        @self._app.get("/tools")
        async def list_tools():
            """List all tools exposed by this agent (MCP ListTools equivalent)."""
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema or {"type": "object"},
                    }
                    for tool in self._tools.values()
                ]
            }

        @self._app.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, arguments: dict = {}):
            """
            Call a specific tool (MCP CallTool equivalent).

            This endpoint mirrors the MCP CallToolRequest/CallToolResult flow.
            """
            if tool_name not in self._tools:
                return {
                    "error": f"Tool '{tool_name}' not found",
                    "available_tools": list(self._tools.keys()),
                }

            tool = self._tools[tool_name]

            try:
                result = await tool.handler(arguments)
                return result
            except Exception as e:
                return {
                    "error": str(e),
                    "tool": tool_name,
                    "agent": self.name,
                }

    async def start(self):
        """Start the agent server."""
        self._running = True
        print(f"🤖 Agent '{self.name}' starting on port {self.port}")

        config = uvicorn.Config(
            self._app,
            host="0.0.0.0",
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def run(self):
        """Run the agent server (blocking, for standalone execution)."""
        self._running = True
        print(f"🤖 Agent '{self.name}' running on port {self.port}")

        uvicorn.run(
            self._app,
            host="0.0.0.0",
            port=self.port,
            log_level="info",
        )

    async def stop(self):
        """Stop the agent server."""
        self._running = False
        print(f"🛑 Agent '{self.name}' stopped")
