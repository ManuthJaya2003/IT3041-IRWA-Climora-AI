"""Regression tests for plan-aware quota accounting."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import usage_service  # noqa: E402
from app.agents.recommendation_agent.recommendation_agent import (  # noqa: E402
    RecommendationAgent,
    detect_crop,
)


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


def test_crop_detection_supports_english_sinhala_and_tamil():
    assert detect_crop("I grow tea in Nuwara Eliya") == "tea"
    assert detect_crop("මම පොල් වගා කරන ගොවියෙක්") == "coconut"
    assert detect_crop("நான் தேயிலை விவசாயி") == "tea"
    assert detect_crop("I grow rice in Jaffna") == "rice"


def test_recommendations_keep_role_specific_guidance_for_all_user_types():
    generic = [{
        "action": "Monitor local conditions",
        "priority": "short-term",
        "explanation": "Stay informed.",
        "category": "awareness",
    }]

    for user_type in (
        "individual", "student", "farmer",
        "business", "organization", "institution",
    ):
        recommendations = RecommendationAgent._filter_for_user_type(
            generic.copy(), user_type
        )
        assert recommendations
        assert any(
            rec["category"] in {
                "preparedness", "awareness", "agriculture", "continuity",
                "community", "safety", "operations", "coordination",
                "facility", "protection",
            }
            for rec in recommendations
        )
