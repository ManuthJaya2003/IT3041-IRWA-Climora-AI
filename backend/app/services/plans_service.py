"""Commercial plans — single source of truth for tiers, pricing and quotas.

The frontend pricing page renders from ``GET /api/v1/billing/plans`` which
serves this data; ``FALLBACK`` copies in the frontend are only used when
the backend is unreachable. Prices in LKR (home market) with USD reference.
Annual billing = 10x monthly (2 months free).
"""

from copy import deepcopy

PLANS: dict[str, dict] = {
    "free": {
        "id": "free",
        "name": "Free",
        "audience": "Individuals & students",
        "tagline": "Everyday climate awareness for Sri Lanka.",
        "monthly_lkr": 0,
        "annual_lkr": 0,
        "monthly_usd": 0,
        "annual_usd": 0,
        "cta": "Get started",
        "highlighted": False,
        "queries_per_day": 100,
        "max_saved_locations": 1,
        "history_days": 7,
        "features": [
            "100 AI climate queries / day",
            "Current weather + hazard risk",
            "English, Sinhala & Tamil",
            "Voice input with audio answers",
            "1 saved location",
            "7-day chat history",
        ],
        "limits_note": "Fair-use daily quota applies.",
    },
    "premium": {
        "id": "premium",
        "name": "Premium",
        "audience": "Individuals, professionals & small teams",
        "tagline": "Personal monitoring and richer analysis.",
        "monthly_lkr": 1490,
        "annual_lkr": 14900,
        "monthly_usd": 5,
        "annual_usd": 50,
        "cta": "Go Premium",
        "highlighted": True,
        "queries_per_day": 1000,
        "max_saved_locations": 5,
        "history_days": 90,
        "features": [
            "Everything in Free, plus:",
            "1,000 AI climate queries / day",
            "Severe-weather browser alerts",
            "5 saved locations",
            "90-day chat history",
            "Priority support",
        ],
        "limits_note": "Per-user fair use.",
    },
    "business": {
        "id": "business",
        "name": "Business",
        "audience": "SMEs & organizations",
        "tagline": "Climate intelligence for operations.",
        "monthly_lkr": 9900,
        "annual_lkr": 99000,
        "monthly_usd": 33,
        "annual_usd": 330,
        "cta": "Start Business trial",
        "highlighted": False,
        "queries_per_day": 10000,
        "max_saved_locations": 25,
        "history_days": 365,
        "features": [
            "Everything in Premium, plus:",
            "10,000 AI climate queries / day",
            "25 saved locations",
            "1-year chat history",
            "API access for integrations",
            "Email support",
        ],
        "limits_note": "Fair use for operations.",
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise",
        "audience": "Large orgs, NGOs & authorities",
        "tagline": "Custom deployment and support.",
        "monthly_lkr": None,
        "annual_lkr": None,
        "monthly_usd": None,
        "annual_usd": None,
        "cta": "Contact sales",
        "highlighted": False,
        "queries_per_day": 0,  # 0 = unlimited
        "max_saved_locations": 0,  # 0 = unlimited
        "history_days": 0,  # 0 = unlimited
        "features": [
            "Unlimited queries (custom quota)",
            "SSO, audit logs & security review",
            "Dedicated / on-premise deployment",
            "Custom integrations & SLA",
            "Staff training & support",
        ],
        "limits_note": "Custom contract.",
    },
}

PLAN_IDS = tuple(PLANS.keys())
DEFAULT_PLAN_ID = "free"


def get_plan(plan_id: str | None) -> dict:
    """Return the plan definition, falling back to Free for unknown ids."""
    key = (plan_id or DEFAULT_PLAN_ID).lower()
    return PLANS.get(key, PLANS[DEFAULT_PLAN_ID])


def list_plans() -> list[dict]:
    """All plans in display order (deep copies — callers must not mutate)."""
    return [deepcopy(PLANS[pid]) for pid in PLAN_IDS]
