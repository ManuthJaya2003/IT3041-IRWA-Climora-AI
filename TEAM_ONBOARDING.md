# Climora AI — Team Onboarding Guide

## Quick Start (Everyone)

### 1. Clone & Switch to Your Branch

```bash
git clone <repo-url>
cd IT3041-IRWA-Climora-AI

# Switch to your branch
git checkout feature/teammate2/nlp-security-agent      # Teammate 2
git checkout feature/teammate3/ir-verification-agent   # Teammate 3
git checkout feature/teammate4/analysis-recommendation-agent  # Teammate 4
```

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
py -3.12 -m venv venv

# Activate (Windows PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org

# Copy env config
copy .env.example .env
```

### 3. Configure .env

Edit `backend/.env` — you need at minimum:
```
AWS_ACCESS_KEY_ID=<ask Manuth for current keys>
AWS_SECRET_ACCESS_KEY=<ask Manuth for current keys>
AWS_SESSION_TOKEN=<ask Manuth for current token>
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

> Note: AWS tokens are temporary and expire. Ask Manuth for fresh ones when needed.

### 4. Run the Backend (Orchestrator)

```bash
uvicorn app.main:app
```

You should see:
```
✓ LLM service initialized (provider: Bedrock - us.anthropic.claude-sonnet-4-20250514-v1:0)
✓ Embedding service initialized (provider: Bedrock Titan, dim: 384)
✓ FAISS vector store initialized (documents: 8, dim: 384)
```

### 5. Test It Works

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/chat/query -H "Content-Type: application/json" -d "{\"query\": \"flood risk in Colombo\", \"location\": \"Colombo\"}"
```

---

## Architecture Overview

```
User Query → Orchestrator (port 8000)
                │
                ├── Security Agent (port 8100)    ← Teammate 2
                ├── NLP Agent (port 8101)         ← Teammate 2
                ├── IR Agent (port 8102)          ← Teammate 3
                ├── Analysis Agent (port 8103)    ← Teammate 4
                ├── Verification Agent (port 8104)← Teammate 3
                └── Recommendation Agent (port 8105) ← Teammate 4
```

Each agent runs as a separate server. The orchestrator calls them via HTTP (MCP protocol). When an agent isn't running, the orchestrator uses built-in fallbacks.

---

## How to Implement Your Agent

### Step 1: Open Your Agent File

Your file is at `backend/app/agents/<your_agent>/<your_agent>.py`. It already has:
- The class structure
- Registered tools
- Documented inputs/outputs for each tool
- `raise NotImplementedError(...)` where your code goes

### Step 2: Replace NotImplementedError with Real Logic

Each tool is an async function:

```python
async def your_tool(self, arguments: dict) -> dict:
    # arguments contains the input from the orchestrator
    query = arguments.get("query", "")
    
    # Your logic here...
    
    # Return a dict with results
    return {"result": "your output"}
```

### Step 3: Use Available Services

You can use these services that are already built:

```python
# LLM (Claude via Bedrock) — for any AI reasoning
from app.services.llm_service import llm_service

response = await llm_service.invoke_model(
    prompt="Analyze this text...",
    system_prompt="You are a climate expert.",
    max_tokens=500,
    temperature=0.3,
)

# Vector Store (FAISS) — for searching stored documents
from app.services.vector_store_service import vector_store_service

results = await vector_store_service.query_similar(
    query_text="flood risk monsoon",
    top_k=5,
)

# Embeddings — for generating vectors
from app.services.embedding_service import embedding_service

vector = embedding_service.embed_text("some text")
```

### Step 4: Run Your Agent Standalone

```bash
python -m app.agents.nlp_agent.nlp_agent         # port 8101
python -m app.agents.ir_agent.ir_agent           # port 8102
python -m app.agents.analysis_agent.analysis_agent    # port 8103
python -m app.agents.verification_agent.verification_agent  # port 8104
python -m app.agents.recommendation_agent.recommendation_agent  # port 8105
python -m app.agents.security_agent.security_agent    # port 8100
```

### Step 5: Test Your Agent Directly

Once running, test via browser or curl:

```bash
# List your tools
curl http://localhost:8101/tools

# Call a specific tool
curl -X POST http://localhost:8101/tools/process_query -H "Content-Type: application/json" -d "{\"query\": \"flood risk in Colombo\", \"location\": \"Colombo, Sri Lanka\"}"
```

### Step 6: Test with Orchestrator

Run both the orchestrator AND your agent, then send a full query:

```bash
# Terminal 1: Your agent
python -m app.agents.nlp_agent.nlp_agent

# Terminal 2: Orchestrator
uvicorn app.main:app

# Terminal 3: Test
curl -X POST http://localhost:8000/api/v1/chat/query -H "Content-Type: application/json" -d "{\"query\": \"flood risk in Colombo\", \"location\": \"Colombo\"}"
```

The orchestrator auto-detects running agents and uses them instead of fallbacks.

---

## Team Assignments

### Teammate 2: NLP Agent + Security Agent

**Priority: NLP first, Security second**

#### NLP Agent (`backend/app/agents/nlp_agent/nlp_agent.py`)

**Install extra dependencies:**
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

**Tools to implement:**

| Tool | Input | Output | How |
|------|-------|--------|-----|
| `process_query` | `{query, location, user_type}` | `{intent, entities, structured_query, expanded_terms}` | spaCy NER + intent classifier |
| `extract_entities` | `{text}` | `{entities: {location:[], date:[], topic:[], hazard:[]}}` | spaCy NER |
| `expand_query` | `{query, entities}` | `{expanded_terms, expanded_query}` | Synonym lookup / LLM |
| `summarize_text` | `{text, max_length}` | `{summary}` | LLM call |

**Intent categories to detect:**
- `risk_awareness` — "What are the risks..."
- `preparedness` — "What should I prepare..."
- `forecast` — "What's the weather..."
- `trend_analysis` — "How has climate changed..."
- `general_info` — Everything else

**Example implementation for `process_query`:**
```python
async def process_query(self, arguments: dict) -> dict:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    
    query = arguments.get("query", "")
    location = arguments.get("location")
    
    # NER
    doc = nlp(query)
    entities = {
        "location": location or [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")],
        "date": [ent.text for ent in doc.ents if ent.label_ == "DATE"],
        "climate_topic": None,  # detect from keywords
        "hazard_type": None,    # detect from keywords
    }
    
    # Intent classification (keyword-based or LLM)
    intent = self._classify_intent(query)
    
    # Query expansion
    expanded = self._expand_terms(query, entities)
    
    return {
        "intent": intent,
        "entities": entities,
        "structured_query": {"original_query": query, "processed": True},
        "expanded_terms": expanded,
    }
```

#### Security Agent (`backend/app/agents/security_agent/security_agent.py`)

**Tools to implement:**

| Tool | Input | Output | How |
|------|-------|--------|-----|
| `validate_input` | `{query, location, context}` | `{safe, sanitized_query, reason, warnings}` | Regex + rules |
| `check_rate_limit` | `{user_id, action}` | `{allowed, remaining, reset_at}` | In-memory counter |
| `detect_injection` | `{text}` | `{is_injection, confidence, patterns_found}` | Regex patterns |

**Injection patterns to detect:**
```python
INJECTION_PATTERNS = [
    r"ignore (previous|above|all) (instructions|prompts)",
    r"you are now",
    r"system:\s",
    r"<\|.*\|>",
    r"ADMIN:",
    r"forget (everything|your instructions)",
    r"override",
    r"jailbreak",
]
```

---

### Teammate 3: IR Agent + Verification Agent

**Priority: IR first, Verification second**

#### IR Agent (`backend/app/agents/ir_agent/ir_agent.py`)

**Tools to implement:**

| Tool | Input | Output | How |
|------|-------|--------|-----|
| `retrieve_documents` | `{structured_query, entities, top_k}` | `{documents: [{source_name, url, content, snippet, reliability_score, topic, location, date}]}` | FAISS search + external APIs |
| `search_sources` | `{query, sources}` | `{results}` | Hit specific APIs |
| `index_document` | `{content, metadata}` | `{indexed, document_id}` | Add to FAISS |

**Example implementation:**
```python
async def retrieve_documents(self, arguments: dict) -> dict:
    from app.services.vector_store_service import vector_store_service
    
    query = arguments.get("structured_query", {}).get("original_query", "")
    entities = arguments.get("entities", {})
    top_k = arguments.get("top_k", 5)
    
    # Build search query from entities
    search_parts = [query]
    if entities.get("location"):
        search_parts.append(str(entities["location"]))
    if entities.get("climate_topic"):
        search_parts.append(str(entities["climate_topic"]))
    
    search_query = " ".join(search_parts)
    
    # Search FAISS
    faiss_results = await vector_store_service.query_similar(
        query_text=search_query,
        top_k=top_k,
    )
    
    # Also search external APIs
    external_results = await self._search_external_sources(query, entities)
    
    # Combine and format
    documents = []
    for r in faiss_results:
        documents.append({
            "source_name": r["metadata"].get("source", "Unknown"),
            "url": r.get("url"),
            "content": r["content"],
            "snippet": r["content"][:300],
            "reliability_score": r["score"],
            "topic": r["metadata"].get("topic", ""),
            "location": r["metadata"].get("location", ""),
            "date": r["metadata"].get("date", ""),
        })
    
    documents.extend(external_results)
    return {"documents": documents}

async def _search_external_sources(self, query, entities):
    """Search OpenWeatherMap, NOAA, etc."""
    import httpx
    results = []
    
    # Example: OpenWeatherMap
    location = entities.get("location", "")
    if location:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"q": location, "appid": "YOUR_API_KEY"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results.append({
                        "source_name": "OpenWeatherMap",
                        "url": f"https://openweathermap.org/city/{data.get('id','')}",
                        "content": f"Current weather in {location}: {data['weather'][0]['description']}...",
                        "snippet": f"Current: {data['weather'][0]['description']}",
                        "reliability_score": 0.8,
                        "topic": "weather",
                        "location": location,
                        "date": "live",
                    })
        except Exception:
            pass
    
    return results
```

**External APIs to integrate (pick at least 1):**
- OpenWeatherMap (free tier: 60 calls/min)
- Open-Meteo (free, no key needed)
- NOAA Climate Data API (free)

#### Verification Agent (`backend/app/agents/verification_agent/verification_agent.py`)

**Tools to implement:**

| Tool | Input | Output | How |
|------|-------|--------|-----|
| `verify_claims` | `{claims, sources}` | `{verified, confidence, claim_results, warnings}` | LLM comparison |
| `check_source_quality` | `{source_name, source_url, content_date}` | `{reliability_score, category, freshness, notes}` | Rules + date check |
| `cross_reference` | `{claim, sources}` | `{supported_by, contradicted_by, consensus_score}` | LLM + comparison |

**Source quality rules:**
```python
SOURCE_TIERS = {
    "government": 0.9,      # NOAA, DMC, Met dept
    "international_org": 0.85,  # WMO, UN, WHO
    "academic": 0.8,        # Research papers
    "news_major": 0.6,      # Reuters, BBC
    "news_local": 0.5,      # Local outlets
    "blog": 0.3,            # Personal blogs
    "unknown": 0.4,
}
```

**Example verify_claims:**
```python
async def verify_claims(self, arguments: dict) -> dict:
    from app.services.llm_service import llm_service
    
    claims = arguments.get("claims", [])
    sources = arguments.get("sources", [])
    
    if not claims or not sources:
        return {"verified": False, "confidence": 0.3, "claim_results": [], "warnings": ["Insufficient data"]}
    
    # Use LLM to check each claim against sources
    source_text = "\n".join([f"[{s.get('source_name')}]: {s.get('content','')[:300]}" for s in sources[:5]])
    
    prompt = f"""Check if these claims are supported by the sources:
    
Claims: {claims}

Sources:
{source_text}

For each claim, state: SUPPORTED, PARTIALLY_SUPPORTED, or UNSUPPORTED.
Return JSON: {{"claim_results": [{{"claim": "...", "status": "...", "supporting_source": "..."}}], "overall_confidence": 0.0-1.0}}"""
    
    response = await llm_service.invoke_model(prompt=prompt, system_prompt="Return only JSON.", max_tokens=500)
    # Parse response...
    
    return {"verified": True, "confidence": 0.7, "claim_results": [], "warnings": []}
```

---

### Teammate 4: Analysis Agent + Recommendation Agent

**Priority: Analysis first, Recommendation second**

#### Analysis Agent (`backend/app/agents/analysis_agent/analysis_agent.py`)

**Tools to implement:**

| Tool | Input | Output | How |
|------|-------|--------|-----|
| `analyze_climate_data` | `{query, intent, entities, evidence}` | `{summary, risk_level, risk_factors, risk_explanation, detailed_analysis, claims, confidence}` | Risk matrix + LLM |
| `assess_risk` | `{hazard_type, evidence, location, timeframe}` | `{risk_level, confidence, factors}` | Risk matrix |
| `identify_patterns` | `{data_points, topic}` | `{patterns, trend_direction}` | LLM analysis |

**Risk Matrix to implement:**
```python
# Severity (1-5) × Probability (1-5) = Risk Score
# 1-6: Low | 7-12: Moderate | 13-19: High | 20-25: Critical

SEVERITY_KEYWORDS = {
    5: ["death", "catastrophic", "destruction", "collapse"],
    4: ["severe damage", "major disruption", "widespread"],
    3: ["moderate damage", "significant", "disruption"],
    2: ["minor damage", "inconvenience", "localized"],
    1: ["negligible", "minimal", "unlikely"],
}

PROBABILITY_INDICATORS = {
    5: ["imminent", "currently", "active", "ongoing"],
    4: ["very likely", "high probability", "expected"],
    3: ["likely", "moderate probability", "possible"],
    2: ["unlikely", "low probability", "rare"],
    1: ["very unlikely", "extremely rare", "negligible"],
}
```

**Example implementation:**
```python
async def analyze_climate_data(self, arguments: dict) -> dict:
    from app.services.llm_service import llm_service
    
    query = arguments.get("query", "")
    evidence = arguments.get("evidence", [])
    
    # Format evidence for LLM
    evidence_text = "\n".join([
        f"[{doc.get('source_name')}]: {doc.get('content','')[:400]}"
        for doc in evidence[:5]
    ])
    
    # Use LLM for analysis
    prompt = f"""Analyze climate risks based on this evidence:

Query: {query}
Evidence:
{evidence_text}

Provide JSON with: summary, risk_level (low/moderate/high/critical), 
risk_factors (list), risk_explanation, detailed_analysis, claims (list)"""
    
    response = await llm_service.invoke_model(
        prompt=prompt,
        system_prompt="You are a climate risk analyst. Return only valid JSON.",
        max_tokens=800,
        temperature=0.2,
    )
    
    # Parse JSON response
    import json
    try:
        result = json.loads(response)
        # Apply risk matrix validation
        result["risk_level"] = self._validate_risk_level(result, evidence)
        return result
    except:
        return {"summary": "Analysis failed", "risk_level": "unknown", ...}
```

#### Recommendation Agent (`backend/app/agents/recommendation_agent/recommendation_agent.py`)

**Tools to implement:**

| Tool | Input | Output | How |
|------|-------|--------|-----|
| `generate_recommendations` | `{analysis, user_type, location}` | `{recommendations: [{action, priority, explanation, category}], emergency_notice}` | LLM + templates |
| `prioritize_actions` | `{recommendations, risk_level}` | `{prioritized}` | Sort by urgency |
| `personalize_advice` | `{recommendations, user_type, location, context}` | `{personalized}` | LLM adaptation |

**User-type templates:**
```python
USER_TYPE_CONTEXT = {
    "individual": "Focus on personal safety, home protection, emergency kits, evacuation plans",
    "farmer": "Focus on crop protection, irrigation, livestock safety, harvest timing",
    "business": "Focus on supply chain, operations continuity, employee safety, insurance",
    "student": "Focus on understanding risks, school safety, community awareness",
    "organization": "Focus on policy, infrastructure, community planning, resource allocation",
}
```

**Priority rules:**
```python
# If risk_level == "critical" or "high" → at least 1 "immediate" recommendation
# If risk_level == "moderate" → "short-term" focus
# If risk_level == "low" → "long-term" preparedness
```

---

## Testing Checklist

Before submitting, verify your agent works:

- [ ] Agent starts without errors: `python -m app.agents.<your_agent>.<your_agent>`
- [ ] `/health` endpoint returns status
- [ ] `/tools` lists all your tools
- [ ] Each tool returns valid JSON when called directly
- [ ] Works with orchestrator (start both, send a query)
- [ ] No hardcoded API keys in code (use .env)
- [ ] Code has comments explaining your approach

---

## Important Notes

1. **Don't modify orchestrator code** — it auto-detects your agent when it's running
2. **Return the exact output format** documented in your agent file — the orchestrator expects specific keys
3. **Use `llm_service` for any LLM calls** — don't create your own boto3 clients
4. **Handle errors gracefully** — return a dict with `{"error": "message"}` instead of crashing
5. **AWS tokens expire** — ask Manuth for fresh tokens when you see auth errors
6. **Seed the vector store** before testing IR: `curl -X POST http://localhost:8000/api/v1/vectors/seed`

---

## Communication

- All agent communication uses HTTP POST to `/tools/<tool_name>`
- Input: JSON body with arguments
- Output: JSON response with results
- The orchestrator handles all routing — you just implement the tool logic

---

## File Quick Reference

```
Your files:
  backend/app/agents/nlp_agent/nlp_agent.py           ← Teammate 2
  backend/app/agents/security_agent/security_agent.py  ← Teammate 2
  backend/app/agents/ir_agent/ir_agent.py             ← Teammate 3
  backend/app/agents/verification_agent/verification_agent.py  ← Teammate 3
  backend/app/agents/analysis_agent/analysis_agent.py  ← Teammate 4
  backend/app/agents/recommendation_agent/recommendation_agent.py  ← Teammate 4

Shared services (use but don't modify):
  backend/app/services/llm_service.py          ← LLM calls
  backend/app/services/vector_store_service.py ← FAISS search
  backend/app/services/embedding_service.py    ← Generate embeddings

Base class (don't modify):
  backend/app/mcp/base_agent_server.py         ← Your agent inherits from this
```
