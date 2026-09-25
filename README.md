# CLIMORA AI

**Agentic AI-Powered Climate Intelligence & Decision Support System**

IT 3041 – Information Retrieval and Web Analytics | Group Assignment

---

## Overview

Climora AI is a multi-agent climate intelligence platform that combines LLMs, NLP, Information Retrieval, security, and agent-to-agent communication (MCP) to transform climate and environmental information into understandable, evidence-based, and actionable guidance.

A user asks a climate-related question → the system coordinates multiple specialized agents to retrieve, analyze, verify, and explain climate-related information → returns a response with evidence, risk assessment, and practical recommendations.

## Architecture

```
User → React Frontend → FastAPI Backend → Orchestrator Agent (MCP Client)
                                                    │
                              ┌──────────────────────┴──────────────────────┐
                              │         MCP Agent Servers                    │
                              │                                              │
                              │  ┌─────────────┐  ┌─────────────────────┐   │
                              │  │ Security    │  │ NLP Agent           │   │
                              │  │ Agent :8100 │  │ (Intent/NER) :8101  │   │
                              │  └─────────────┘  └─────────────────────┘   │
                              │  ┌─────────────┐  ┌─────────────────────┐   │
                              │  │ IR Agent    │  │ Analysis Agent      │   │
                              │  │ :8102       │  │ (Risk) :8103        │   │
                              │  └─────────────┘  └─────────────────────┘   │
                              │  ┌─────────────┐  ┌─────────────────────┐   │
                              │  │ Verification│  │ Recommendation      │   │
                              │  │ Agent :8104 │  │ Agent :8105         │   │
                              │  └─────────────┘  └─────────────────────┘   │
                              └──────────────────────────────────────────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────┐
                    │                               │                       │
             AWS Bedrock (LLM)               FAISS (Local Vectors)     PostgreSQL
```

## Agent Pipeline Flow

```
User Query
    → Security Agent (validate input)
    → NLP Agent (intent detection, entity extraction)
    → IR Agent (retrieve evidence from sources + FAISS)
    → Analysis Agent (assess risk, identify patterns)
    → Verification Agent (check claims, validate sources)
    → Recommendation Agent (generate actionable guidance)
    → Orchestrator (assemble final response)
    → User
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| LLM | Google Gemini (dev) / AWS Bedrock Claude (prod) |
| Vector DB | FAISS (local) |
| Database | PostgreSQL |
| Agent Communication | MCP (Model Context Protocol) |
| Containerization | Docker, Docker Compose |
| Cloud | AWS (Bedrock, optionally ECS/Lambda) |

## Project Structure

```
IT3041-IRWA-Climora-AI/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Environment configuration
│   │   ├── agents/
│   │   │   ├── orchestrator/          # Orchestrator Agent (MCP Client)
│   │   │   │   ├── orchestrator_agent.py
│   │   │   │   └── mcp_client.py
│   │   │   ├── nlp_agent/             # NLP Agent (MCP Server)
│   │   │   ├── ir_agent/              # IR Agent (MCP Server)
│   │   │   ├── analysis_agent/        # Analysis Agent (MCP Server)
│   │   │   ├── verification_agent/    # Verification Agent (MCP Server)
│   │   │   ├── recommendation_agent/  # Recommendation Agent (MCP Server)
│   │   │   └── security_agent/        # Security Agent (MCP Server)
│   │   ├── mcp/
│   │   │   ├── base_agent_server.py   # Base class for agent MCP servers
│   │   │   └── run_agents.py          # Start all agent servers
│   │   ├── models/
│   │   │   └── schemas.py             # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── chat.py                # Chat API endpoints
│   │   │   ├── agents.py              # Agent status and listing endpoints
│   │   │   ├── health.py              # Health check endpoints
│   │   │   ├── vector_store.py        # Vector store management API
│   │   │   └── speech.py              # Text-to-Speech & voice query API
│   │   └── services/
│   │       ├── llm_service.py         # Unified LLM (Gemini/Bedrock/Mock)
│   │       ├── bedrock_service.py     # AWS Bedrock LLM integration
│   │       ├── embedding_service.py   # Titan & TF-IDF embeddings
│   │       ├── vector_store_service.py # FAISS local vector store
│   │       ├── language_service.py    # Language detection (English/Sinhala/Tamil)
│   │       └── tts_service.py         # Text-to-Speech audio service
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx      # Main chat UI
│   │   │   ├── ChatMessage.tsx        # Message display with rich data
│   │   │   ├── Header.tsx
│   │   │   └── Sidebar.tsx
│   │   └── api/
│   │       └── climoraApi.ts          # Backend API client
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12+ 
- Node.js 20+
- Google Gemini API key (free) OR AWS Bedrock access
- Docker & Docker Compose (optional, for containerized setup)

### Option 1: Local Development (Recommended for now)

#### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
copy .env.example .env
# Edit .env with your actual credentials

# Run the backend server
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

The frontend will be at `http://localhost:5173` and proxies API calls to the backend at `http://localhost:8000`.

#### Running Agent Servers

All 6 specialized agents (Security, NLP, IR, Analysis, Verification, Recommendation) are fully implemented. 

- **Automatic Start (Default):** When you run `uvicorn app.main:app --reload --port 8000`, the FastAPI server automatically spawns all 6 agent MCP servers on their designated ports (8100–8105) in background subprocesses.
- **Manual Start (Optional/Testing):** You can also run the agent MCP servers independently:

```bash
cd backend

# Run all agents
python -m app.mcp.run_agents

# Or run specific agents (e.g., nlp, ir, security)
python -m app.mcp.run_agents nlp ir

# Or run an agent standalone
python -m app.agents.nlp_agent.nlp_agent
```

### Option 2: Docker Compose

```bash
# Start all services (backend + frontend + database)
docker-compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# Database: localhost:5432
```

## Environment Configuration

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key (free) | For LLM (recommended) |
| `AWS_ACCESS_KEY_ID` | AWS access key | For Bedrock (alternative) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | For Bedrock (alternative) |
| `AWS_REGION` | AWS region (default: us-east-1) | For Bedrock |
| `BEDROCK_MODEL_ID` | Bedrock model ID | For Bedrock |
| `DATABASE_URL` | PostgreSQL connection string | For persistence |
| `SECRET_KEY` | App secret key | For security |

**Note:** The system runs in **mock mode** if credentials are not provided. This means the full pipeline works end-to-end with placeholder responses — useful for development and testing.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/query` | Send a climate query through the multi-agent pipeline |
| GET | `/api/v1/agents/list` | List all active agents, roles, and ports |
| GET | `/api/v1/agents/status` | Real-time agent MCP connection status |
| POST | `/api/v1/speech/speak` | Synthesize speech audio from text (TTS) |
| POST | `/api/v1/speech/query` | Voice query processing with audio response |
| GET | `/api/v1/vectors/stats` | Vector store document count and stats |
| POST | `/api/v1/vectors/search` | Direct semantic search in FAISS |
| GET | `/health` | Basic health check |
| GET | `/health/detailed` | Detailed health with individual service status |

### Example Query

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the flood risks in Colombo this week?",
    "location": "Colombo, Sri Lanka",
    "user_type": "individual"
  }'
```

## Agent Communication (MCP)

Agents communicate via **Model Context Protocol (MCP)**:

- **Orchestrator** = MCP Client (calls tools on other agents)
- **All other agents** = MCP Servers (expose tools for the orchestrator)

Each agent inherits from `BaseAgentServer` and registers tools:

```python
from app.mcp.base_agent_server import BaseAgentServer

class MyAgent(BaseAgentServer):
    def __init__(self):
        super().__init__(name="my_agent", port=8101)
        self.register_tool("my_tool", self.my_tool_handler, "Description")

    async def my_tool_handler(self, arguments: dict) -> dict:
        # Process the task
        return {"result": "done"}
```

## Team Responsibilities

| Member | Component | Files |
|--------|-----------|-------|
| Member 1 | Orchestrator Agent, Backend Infrastructure, MCP Setup | `orchestrator/`, `mcp/`, `services/`, `config.py`, `main.py` |
| Member 2 | NLP Agent + Security Agent | `nlp_agent/`, `security_agent/` |
| Member 3 | IR Agent + Verification Agent | `ir_agent/`, `verification_agent/` |
| Member 4 | Analysis Agent + Recommendation Agent | `analysis_agent/`, `recommendation_agent/` |

## Development Notes

- **Multi-Agent Pipeline**: All 6 specialized agents (Security :8100, NLP :8101, IR :8102, Analysis :8103, Verification :8104, Recommendation :8105) are fully implemented with both deterministic rule engines and LLM enrichment.
- **Resilience & Fallback**: The orchestrator has built-in fallback logic — if an agent server is temporarily unreachable, it seamlessly falls back to direct services or LLM calls.
- **Unified Startup**: Running `uvicorn app.main:app --reload --port 8000` automatically manages the lifecycle of all agent servers in background subprocesses.
- **Standalone Mode**: All agents can also be run standalone for isolated debugging (e.g. `python -m app.agents.nlp_agent.nlp_agent`).
- **Offline / Mock Capable**: The backend and frontend function end-to-end even without external API keys or cloud credentials.

## Responsible AI

- Responses are grounded in retrieved evidence (not pure LLM generation)
- Verification Agent checks claims before they reach users
- Sources and confidence scores are shown to users
- Disclaimers are included for all responses
- Input validation and security checks on all queries
- Uncertainty is communicated clearly

## License

University project — IT 3041 Information Retrieval and Web Analytics.
