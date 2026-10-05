# CLIMORA AI

**Agentic AI-Powered Climate Intelligence & Decision Support System — v1.0**

IT 3041 – Information Retrieval and Web Analytics · Group Assignment · Final Product

---

## Overview

Climora AI is a multi-agent climate intelligence platform for Sri Lanka. A user asks a
climate question in **English, Sinhala, or Tamil** → an orchestrator coordinates **7 specialized
agents** (security, NLP, retrieval, analysis, verification, recommendation) → the user gets an
evidence-grounded answer with a risk assessment, recommendations, sources, and confidence score.

```text
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

### Agent pipeline

```text
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

## Key features

- **Trilingual** — language auto-detected by script; answers in English, Sinhala, or Tamil, with voice input + audio answers
- **Evidence-grounded** — every answer cites sources with reliability scores and confidence
- **Risk-aware** — transparent risk levels with explanations, plus opt-in severe-weather browser alerts
- **Commercial tiers that actually enforce** — Free / Premium / Business / Enterprise with live daily quotas, plan-limited saved locations, history retention caps, and Premium-gated alerts
- **Real settings system** — appearance (light/dark/system), personalization, notifications, data export & retention, subscription management
- **Secure by default** — input validation, admin-token protected endpoints, rate limiting, per-plan quotas, no internal errors leaked
- **Resilient** — agent fallbacks keep the pipeline answering even if an agent server is down; runs fully offline in mock mode

### Production integration notes

The local prototype provides plan and subscription UI, and paid checkout now
opens a server-created Stripe Checkout Session. Paid entitlements are not yet
bound to authenticated accounts or activated from verified Stripe webhooks.
Do not treat the client-supplied `X-Plan` header as an entitlement in
production until identity, payment webhooks, and server-side plan records are
connected.

Browser alert preferences are implemented, but continuous weather monitoring
and push delivery require a production scheduler, notification provider, and
device registration.

Web Push alerting is now implemented behind VAPID configuration. Set
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT` in the deployment
environment, enable alerts from Settings on an HTTPS origin, and use the
browser's test notification button to verify delivery. The backend stores
subscriptions in PostgreSQL, checks subscribed locations periodically, and
deduplicates severe rain, wind, and heat alerts.

The agent servers expose MCP-compatible HTTP tool routes for the current
development deployment. A production deployment should use authenticated MCP
transport or an equivalent authenticated service-to-service channel.

### Multi-user Docker deployment

The development stack is in `docker-compose.yml`. For a server deployment, use
`docker-compose.prod.yml`, which builds immutable backend/frontend images,
keeps PostgreSQL on the private Compose network, disables reload and source
bind-mounts, and exposes only the frontend.

On the deployment host:

```bash
cp .env.prod.example .env.prod
# Edit .env.prod and provide real random values and provider credentials.
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

The application is then available at `PUBLIC_ORIGIN` on `HTTP_PORT`. Put a TLS
reverse proxy in front of the frontend for HTTPS before exposing it publicly.
This deployment improves process and network isolation, but it does not replace
the still-pending authenticated user accounts and server-side subscription
entitlements.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic |
| LLM | Google Gemini (dev) / AWS Bedrock Claude (prod) / offline mock |
| Vector DB | FAISS (local, 187 seeded climate documents) |
| Database | PostgreSQL (chat-history persistence; Docker Compose supported) |
| Agent communication | MCP (Model Context Protocol) |
| Speech | Web Speech API (input) + gTTS (audio answers) |
| Deployment | Docker, Docker Compose, Nginx |

## Project structure

```text
IT3041-IRWA-Climora-AI/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Environment configuration
│   │   ├── agents/
│   │   │   ├── orchestrator/          # Orchestrator Agent (MCP Client)
│   │   │   │   ├── orchestrator_agent.py
│   │   │   │   ├── mcp_client.py
│   │   │   │   └── shared.py          # Shared singleton across routers
│   │   │   ├── nlp_agent/             # NLP Agent (MCP Server :8101)
│   │   │   ├── ir_agent/              # IR Agent (MCP Server :8102)
│   │   │   ├── analysis_agent/        # Analysis Agent (MCP Server :8103)
│   │   │   ├── verification_agent/    # Verification Agent (MCP Server :8104)
│   │   │   ├── recommendation_agent/  # Recommendation Agent (MCP Server :8105)
│   │   │   └── security_agent/        # Security Agent (MCP Server :8100)
│   │   ├── mcp/
│   │   │   ├── base_agent_server.py   # Base class for agent MCP servers
│   │   │   └── run_agents.py          # Start all agent servers
│   │   ├── models/
│   │   │   └── schemas.py             # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── chat.py                # Chat API endpoints + session history
│   │   │   ├── agents.py              # Agent status and listing endpoints
│   │   │   ├── health.py              # Health check endpoints
│   │   │   ├── vector_store.py        # Vector store management API (admin-guarded)
│   │   │   ├── speech.py              # Text-to-Speech & voice query API
│   │   │   ├── billing.py             # Plans catalogue + quota usage API
│   │   │   └── deps.py                # Admin auth, rate limit, quota dependencies
│   │   └── services/
│   │       ├── llm_service.py         # Unified LLM (Gemini/Bedrock/Mock)
│   │       ├── bedrock_service.py     # AWS Bedrock LLM integration
│   │       ├── embedding_service.py   # Titan & TF-IDF embeddings
│   │       ├── vector_store_service.py # FAISS local vector store
│   │       ├── language_service.py    # Language detection (English/Sinhala/Tamil)
│   │       ├── tts_service.py         # Text-to-Speech audio service
│   │       ├── plans_service.py       # Commercial tiers, pricing, quotas
│   │       └── usage_service.py       # Daily per-plan quota tracking
│   ├── tests/                         # API regression tests (pytest)
│   │   ├── test_api_guards.py
│   │   └── test_billing.py
│   ├── scripts/
│   │   └── evaluate_ir.py             # Offline IR evaluation harness
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── settings.ts               # Settings load/save/validation + theme
│   │   ├── plans.ts                  # Plan catalogue fallback + saved locations
│   │   ├── usageBus.ts               # Real-time quota refresh events
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx      # Main chat UI
│   │   │   ├── ChatMessage.tsx        # Message display with rich data
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx            # History + live quota meter
│   │   │   ├── SettingsView.tsx       # Full settings page (7 sections)
│   │   │   └── PlansModal.tsx         # Pricing tiers + plan switching
│   │   ├── hooks/
│   │   │   └── useSpeechRecognition.ts # Web Speech API wrapper
│   │   └── api/
│   │       └── climoraApi.ts          # Backend API client
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── DEPLOYMENT.md                      # Local / Docker / production guide
├── EVALUATION.md                      # Measured results + limitations
├── DEMO.md                            # Viva demo script
└── README.md
```

## Getting started

### Prerequisites

- Python 3.12+, Node.js 20+
- Google Gemini API key (free) **or** AWS Bedrock access (optional — mock mode works without either)
- Docker & Docker Compose (optional)

### Option 1 — Local development

```bash
# Backend (terminal 1)
cd backend
python -m venv venv
venv\Scripts\activate        # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env       # then set GEMINI_API_KEY if you have one
uvicorn app.main:app --port 8000
```

```bash
# Frontend (terminal 2)
cd frontend
npm install
npm run dev                  # http://localhost:5173 (proxies /api → :8000)
```

The backend auto-starts all 6 agent MCP servers (ports 8100–8105) on launch.
Agents can also run standalone for debugging: `python -m app.mcp.run_agents`.

### Option 2 — Docker Compose

```bash
copy backend\.env.example backend\.env
docker compose up --build
# Frontend: http://localhost:3000 · Backend: http://localhost:8000 · DB: localhost:5432
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the production checklist and cloud sketch.

## Environment configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini key (free tier, recommended for dev) | No (mock mode otherwise) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Bedrock credentials (production LLM) | No |
| `OPENWEATHER_API_KEY` | Live weather readings | No |
| `DATABASE_URL` | PostgreSQL connection string | No (FAISS files used) |
| `SECRET_KEY` | App secret — change in production | Yes for prod |
| `ADMIN_TOKEN` | Guards mutating vector endpoints (`X-Admin-Token`) | Yes for prod |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | Per-IP rate limiting (default 100/min) | No |
| `CORS_ORIGINS` | Allowed frontend origins | Yes for prod |

When `ENVIRONMENT=production`, the backend fails closed unless `DEBUG=false`,
`SECRET_KEY` and `ADMIN_TOKEN` are at least 32 characters, and every
`CORS_ORIGINS` value is an explicit HTTPS origin. Local development keeps its
permissive defaults.

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/query` | Full multi-agent pipeline (rate-limited + quota-enforced) |
| GET | `/api/v1/chat/history?session_id=…` | Stored conversation turns |
| POST | `/api/v1/speech/voice-query` | Voice query + TTS audio response |
| POST | `/api/v1/speech/speak` | Text-to-speech synthesis |
| GET | `/api/v1/billing/plans` | Tiers, pricing, quotas, features |
| GET | `/api/v1/billing/usage` | Caller plan + daily quota state |
| GET | `/api/v1/agents/list` · `/api/v1/agents/status` | Agent catalogue + live MCP status |
| GET | `/api/v1/vectors/stats` · `/search` · `/documents` | Read-only vector store access |
| POST/DELETE | `/api/v1/vectors/…` | Mutations — require `X-Admin-Token` when configured |
| GET | `/health` · `/health/detailed` | Health checks |

Example:

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" -H "X-Plan: premium" \
  -d '{"query": "Is there a flood risk in Kandy right now?", "user_type": "farmer"}'
```

## Evaluation

Measured, re-runnable — full detail in [EVALUATION.md](./EVALUATION.md):

- Location extraction **100%** · topic detection **100%** (16 queries, EN/SI/TA)
- FAISS top-3 retrieval hit rate **81.2%** (TF-IDF + cross-lingual bridge; live APIs + LLM synthesis compensate in production)
- 16 backend regression tests · strict `tsc` + production frontend build

```bash
cd backend
python scripts/evaluate_ir.py
python tests/test_billing.py && python tests/test_api_guards.py
```

## Commercialization

| Plan | Price (LKR) | Daily queries | Enforced limits |
|------|-------------|---------------|-----------------|
| Free | 0 | 100 | 1 saved location · 7-day history |
| Premium | 1,490/mo · 14,900/yr | 1,000 | Alerts · 5 locations · 90-day history |
| Business | 9,900/mo · 99,000/yr | 10,000 | 25 locations · 1-year history · API access |
| Enterprise | Custom | Unlimited | SSO · dedicated deploy · SLA |

Quotas and limits are enforced in code, not just displayed. Annual billing = 10× monthly.
Upgrades go through a demo checkout (order summary → card form → receipt, clearly
labeled — no payment provider); chat history persists to PostgreSQL when configured,
memory otherwise.

## Responsible AI

- Answers grounded in retrieved evidence, never pure LLM generation
- Verification agent checks claims; confidence scores and sources shown
- Transparent risk criteria with explanations; uncertainty communicated
- Disclaimers on every response; no internal errors leaked to users
- Minimal data collection; conversations stay in the browser unless exported

## Team

| # | Name | Student ID | GitHub | Responsibility |
|---|------|------------|--------|----------------|
| Member 1 | JAYASEKARA M. E. | IT23728776 | [@ManuthJaya2003](https://github.com/ManuthJaya2003) | Orchestrator Agent, backend infrastructure, MCP setup |
| Member 2 | SASRA M. H. F. | IT23693586 | [@shazraHallaj12](https://github.com/shazraHallaj12) | Analysis Agent, Recommendation Agent |
| Member 3 | GUNATHILAKE L. L. S. W. | IT23744066 | [@lashi10976-git](https://github.com/lashi10976-git) | NLP Agent, Security Agent |
| Member 4 | MADUGALLE K. J. W. R. E. W. N. M. R. O. D. | IT23555594 | [@OsandaMadugalle](https://github.com/OsandaMadugalle) | IR Agent, Verification Agent, frontend, billing & settings |

## License

University project — IT 3041 Information Retrieval and Web Analytics.
