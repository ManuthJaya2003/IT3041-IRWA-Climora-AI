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


def test_greetings_are_classified_as_free_queries():
    assert usage_service.is_free_greeting("  Good morning ") is True
    assert usage_service.is_free_greeting("Good morning!") is True
    assert usage_service.is_free_greeting("Hello, Climora AI!") is True
    assert usage_service.is_free_greeting("සුභ උදෑසනක්!") is True
    assert usage_service.is_free_greeting("ආයුබෝවන්") is True
    assert usage_service.is_free_greeting("How are you?") is True
    assert usage_service.is_free_greeting("வணக்கம்!") is True
    assert usage_service.is_free_greeting("காலை வணக்கம்") is True
    assert usage_service.is_free_greeting("எப்படி இருக்கிறீர்கள்?") is True
    assert usage_service.is_free_greeting("weather in Kandy") is False


def test_time_based_greetings_are_classified_as_free_queries():
    assert usage_service.is_free_greeting("Good morning!") is True
    assert usage_service.is_free_greeting("Good afternoon") is True
    assert usage_service.is_free_greeting("Good evening") is True
