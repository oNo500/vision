"""Tests for persona injection in build_director_prompt."""
from src.live.director_agent import build_director_prompt


def _base_state():
    return {
        "segment_id": "s1",
        "title": "开场",
        "goal": "hello",
        "cue": [],
        "must_say": False,
        "keywords": [],
        "remaining_seconds": 30,
    }


def test_persona_ctx_appears_in_prompt():
    prompt = build_director_prompt(
        script_state=_base_state(),
        knowledge_ctx="product knowledge",
        recent_events=[],
        last_said="",
        persona_ctx="主播：小美 | 风格：热情 | 禁用词：骗子",
    )
    assert "小美" in prompt
    assert "骗子" in prompt


def test_persona_ctx_empty_does_not_break():
    prompt = build_director_prompt(
        script_state=_base_state(),
        knowledge_ctx="product knowledge",
        recent_events=[],
        last_said="",
        persona_ctx="",
    )
    assert "product knowledge" in prompt


def test_persona_ctx_default_is_empty():
    """Calling without persona_ctx should not raise."""
    prompt = build_director_prompt(
        script_state=_base_state(),
        knowledge_ctx="product knowledge",
        recent_events=[],
        last_said="",
    )
    assert isinstance(prompt, str)
