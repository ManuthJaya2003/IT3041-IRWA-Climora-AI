# Climora AI — Deployment Guide

## Plans & pricing (commercialization)

Four tiers, served by the backend as the single source of truth
(`GET /api/v1/billing/plans`) and rendered in the app (sidebar →
**Upgrade plan**):

| Plan | Price (LKR) | Daily AI queries | Highlights |
|------|-------------|------------------|------------|
| Guest trial | 0 | 2 | Try before registering |
| Free | 0 | 100 (account) | Weather + hazard risk, 3 languages, 1 location |
| Premium | 1,490/mo · 14,900/yr | 1,000 | Alerts, 5 locations, 90-day history, voice |
| Business | 9,900/mo · 99,000/yr | 10,000 | 5 seats, API access, dashboards, reports |
| Enterprise | Custom | Unlimited | Organizations, OIDC SSO, audit log, dedicated/on-premise deploy |

Annual billing = 10× monthly (2 months free). Quotas are enforced
server-side per account (`GET /api/v1/billing/usage` shows live usage);
enterprise members inherit unlimited quota via their organization.

### Enterprise SSO setup (owner)

1. Create the organization: **Settings → Organization** (or Plans → Enterprise → Set up organization).
2. In your identity provider (Okta, Entra ID, Auth0, Google Workspace),
   register an app with redirect URI
   `<backend-origin>/api/v1/auth/sso/callback`.
3. Paste the issuer URL + client ID (+ secret if required) into the
   Organization panel. Members sign in via **Sign in → Enterprise SSO**
   with the org slug; matching email domains are auto-provisioned.

### Dedicated deploy

`docker-compose.prod.yml` is already a single-tenant stack (private
PostgreSQL network, only the frontend exposed). A dedicated enterprise
deployment = one private stack per customer with its own `.env.prod`
(SECRET_KEY, ADMIN_TOKEN, OIDC origins) behind their TLS reverse proxy.

## Option 1 — Local development

```bash
# Backend
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then set GEMINI_API_KEY / tokens
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api → :8000)
```

## Option 2 — Docker Compose (recommended for evaluation)

```bash
cp backend/.env.example backend/.env   # compose reads this file
docker compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000  (docs: /docs)
# Database: localhost:5432
```

Notes:
- The backend container auto-starts all 6 agent MCP servers (ports
  8100–8105, container-internal).
- `frontend/nginx.conf` proxies `/api` and `/health` to `backend:8000`,
  so the production build needs no extra API configuration.
- Vector data persists via the `./backend` bind mount
  (`backend/vector_data/`, `backend/audio_cache/`).

## Production checklist

1. `SECRET_KEY` — long random value; `ADMIN_TOKEN` — strong token, sent
   as `X-Admin-Token` for seed/reset/add/delete vector endpoints.
2. `ENVIRONMENT=production`, `DEBUG=false`; restrict `CORS_ORIGINS` to
   the real frontend origin.
3. Terminate TLS at a reverse proxy (or cloud load balancer) — the app
   itself serves plain HTTP.
4. Back up `backend/vector_data/` (FAISS index + documents) and rotate
   `backend/audio_cache/` (TTS files regenerate on demand).
5. Set quotas per tier via the plans service; monitor
   `GET /api/v1/billing/usage` and backend logs for abuse.
6. PostgreSQL service is included for future persistence; the current
   release stores vectors on disk and sessions in memory.

## Cloud sketch (AWS)

ECR/ECS (or EC2) for backend + frontend containers → ALB with HTTPS →
RDS PostgreSQL when persistence is switched on → Bedrock for the LLM
(swap `GEMINI_API_KEY` for Bedrock credentials). Secrets in AWS
Secrets Manager, never in images.
