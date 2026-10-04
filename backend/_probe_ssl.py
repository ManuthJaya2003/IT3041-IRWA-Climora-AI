"""Verify the certifi SSL context lets the geocoding call succeed."""
import asyncio


async def main():
    from app.agents.ir_agent.ir_agent import _http_get_with_retry, _SSL_CONTEXT
    print("SSL context type:", type(_SSL_CONTEXT).__name__)

    resp = await _http_get_with_retry(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": "Anuradhapura", "count": 1, "language": "en", "format": "json"},
    )
    if resp is None:
        print("RESULT: still failing (resp is None)")
        return
    results = resp.json().get("results") or []
    if results:
        r = results[0]
        print(f"RESULT: OK -> {r.get('name')} @ {r.get('latitude')},{r.get('longitude')}")
    else:
        print("RESULT: connected OK but no geocoding results")


if __name__ == "__main__":
    asyncio.run(main())
