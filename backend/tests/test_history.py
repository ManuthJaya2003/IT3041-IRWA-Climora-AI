"""History service tests: memory cache, SQL persistence, PG fallback.

Run with:  python -m pytest tests/test_history.py
(or directly:  python tests/test_history.py)
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.history_service import HistoryService  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_memory_backend_round_trip():
    svc = HistoryService()
    assert _run(svc.initialize("")) == "memory"
    svc.store_turn("s1", "flood in Kandy?", "High risk.")
    svc.store_turn("s1", "what next?", "Prepare a kit.")
    turns = svc.get_turns("s1")
    assert [t["query"] for t in turns] == ["flood in Kandy?", "what next?"]
    assert turns[0]["response_summary"] == "High risk."
    assert svc.get_turns("unknown") == []


def test_memory_caps_at_fifty():
    svc = HistoryService()
    for i in range(60):
        svc.store_turn("s2", f"q{i}", "a")
    assert len(svc.get_turns("s2")) == 50
    assert svc.get_turns("s2")[0]["query"] == "q10"


def test_unreachable_postgres_falls_back_to_memory():
    svc = HistoryService()
    backend = _run(svc.initialize("postgresql://u:p@127.0.0.1:9/db"))
    assert backend == "memory"
    svc.store_turn("s3", "hello", "hi")
    assert svc.get_turns("s3")[0]["query"] == "hello"


def test_sql_persistence_survives_restart():
    # Same SQL path as PostgreSQL, using a file DB (no server needed).
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{tmp}/history.db"
        svc1 = HistoryService()
        assert _run(svc1.initialize(url)) == "sqlite"
        svc1.store_turn("sess", "drought in Jaffna?", "Moderate risk.")
        svc1.close()  # release the file so a new process could open it
        # Fresh instance, same file — simulates a backend restart.
        svc2 = HistoryService()
        try:
            assert _run(svc2.initialize(url)) == "sqlite"
            turns = svc2.get_turns("sess")
            assert len(turns) == 1
            assert turns[0]["query"] == "drought in Jaffna?"
            assert turns[0]["response_summary"] == "Moderate risk."
        finally:
            svc2.close()


if __name__ == "__main__":
    tests = [
        test_memory_backend_round_trip,
        test_memory_caps_at_fifty,
        test_unreachable_postgres_falls_back_to_memory,
        test_sql_persistence_survives_restart,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
