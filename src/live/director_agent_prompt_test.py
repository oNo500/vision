"""Tests for build_director_prompt with new ScriptSegment fields."""
from src.live.director_agent import build_director_prompt


_DEFAULT_CUE = ["2000亿活性益生菌", "72小时补水"]


def _state(must_say=False, cue=_DEFAULT_CUE):
    return {
        "segment_id": "s1",
        "title": "产品介绍",
        "goal": "重点讲解益生菌成分，引导观众点购物车",
        "cue": cue,
        "must_say": must_say,
        "keywords": ["益生菌", "购物车"],
        "remaining_seconds": 600,
    }


def test_prompt_contains_title():
    prompt = build_director_prompt(_state(), "产品知识", [])
    assert "产品介绍" in prompt


def test_prompt_contains_goal():
    prompt = build_director_prompt(_state(), "产品知识", [])
    assert "重点讲解益生菌成分" in prompt


def test_prompt_contains_cue_lines():
    prompt = build_director_prompt(_state(), "产品知识", [])
    assert "2000亿活性益生菌" in prompt
    assert "72小时补水" in prompt


def test_prompt_must_say_false_label():
    prompt = build_director_prompt(_state(must_say=False), "产品知识", [])
    assert "尽量覆盖" in prompt


def test_prompt_must_say_true_label():
    prompt = build_director_prompt(_state(must_say=True), "产品知识", [])
    assert "必须全部逐字说出" in prompt


def test_prompt_empty_cue_no_section():
    prompt = build_director_prompt(_state(cue=[]), "产品知识", [])
    assert "锚点话术" not in prompt
