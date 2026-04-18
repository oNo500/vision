"""Tests for SessionManager.load_plan and plan-driven _build_and_start."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.live.session import SessionManager, _build_persona_ctx, _build_knowledge_ctx_from_plan
from vision_shared.event_bus import EventBus


def _make_plan() -> dict:
    return {
        "id": "plan-1",
        "name": "Test Plan",
        "product": {
            "name": "好产品", "description": "很好", "price": "99",
            "highlights": ["亮点1"], "faq": [{"question": "Q", "answer": "A"}],
        },
        "persona": {
            "name": "小美", "style": "热情",
            "catchphrases": ["买它!"], "forbidden_words": ["骗子"],
        },
        "script": {
            "segments": [
                {"id": "s1", "title": "开场", "goal": "欢迎来到直播间", "duration": 60,
                 "cue": ["欢迎"], "must_say": True, "keywords": ["好产品"]},
            ]
        },
    }


def test_load_plan_sets_active_plan():
    bus = MagicMock(spec=EventBus)
    sm = SessionManager(bus)
    assert sm.get_active_plan() is None
    plan = _make_plan()
    sm.load_plan(plan)
    assert sm.get_active_plan()["id"] == "plan-1"


def test_build_persona_ctx():
    persona = {"name": "小美", "style": "热情",
               "catchphrases": ["买它!"], "forbidden_words": ["骗子"]}
    ctx = _build_persona_ctx(persona)
    assert "小美" in ctx
    assert "骗子" in ctx
    assert "买它!" in ctx


def test_build_knowledge_ctx_from_plan():
    product = {
        "name": "好产品", "description": "很好", "price": "99",
        "highlights": ["亮点1"], "faq": [{"question": "Q", "answer": "A"}],
    }
    ctx = _build_knowledge_ctx_from_plan(product)
    assert "好产品" in ctx
    assert "亮点1" in ctx
    assert "Q" in ctx
