"""Regression tests for plan-aware quota accounting."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import usage_service  # noqa: E402


def test_usage_is_tracked_separately_per_plan():
    usage_service.reset_usage_state()
    try:
        allowed, remaining, limit = usage_service.check_and_consume("client", "premium")
        assert (allowed, remaining) == (True, limit - 1)
        assert limit > 0
        assert usage_service.get_usage("client", "premium")["used_today"] == 1
        assert usage_service.get_usage("client", "free")["used_today"] == 0
    finally:
        usage_service.reset_usage_state()
