"""Tests for memory integration in DirectorAgent."""
from __future__ import annotations

from vision_live.director_agent import build_director_prompt, parse_director_response
from vision_live.session_memory import SessionMemory


def _state(segment_id: str = "s1", cue: list[str] | None = None) -> dict:
    return {
        "segment_id": segment_id,
        "title": "产品介绍",
        "goal": "重点讲解益生菌",
        "cue": cue or ["新西兰原装", "买二送一"],
        "must_say": False,
        "keywords": ["益生菌"],
        "remaining_seconds": 600,
    }


# ---------------------------------------------------------------------------
# prompt renders memory sections
# ---------------------------------------------------------------------------


def test_prompt_renders_recent_utterances():
    m = SessionMemory()
    m.record_utterance(text="这款益生菌原装进口", topic_tag=None,
                       utterance_id="x", segment_id="s1", cue_hits=None)
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], memory=m,
    )
    assert "最近说过" in prompt
    assert "这款益生菌原装进口" in prompt


def test_prompt_renders_topic_summary():
    m = SessionMemory()
    m.record_utterance(text="x", topic_tag="成分:益生菌",
                       utterance_id="a", segment_id="s1", cue_hits=None)
    m.record_utterance(text="y", topic_tag="成分:益生菌",
                       utterance_id="b", segment_id="s1", cue_hits=None)
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], memory=m,
    )
    assert "全场已讲话题" in prompt
    assert "成分:益生菌" in prompt
    assert "已讲 2 次" in prompt


def test_prompt_renders_cue_status():
    m = SessionMemory()
    m.record_utterance(text="x", topic_tag=None, utterance_id="x",
                       segment_id="s1", cue_hits=["新西兰原装"])
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], memory=m,
    )
    assert "新西兰原装 ✓ 已说" in prompt
    assert "买二送一 ✗ 未说" in prompt


def test_prompt_renders_recent_qa():
    m = SessionMemory()
    m.record_qa("这个怎么吃", "饭后温水冲服")
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], memory=m,
    )
    assert "最近" in prompt and "问答" in prompt
    assert "怎么吃" in prompt
    assert "温水冲服" in prompt


def test_prompt_without_memory_still_works():
    """Memory is optional — builder must handle None gracefully."""
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], memory=None,
    )
    assert isinstance(prompt, str)
    assert "产品介绍" in prompt


# ---------------------------------------------------------------------------
# parse_director_response with new fields
# ---------------------------------------------------------------------------


def test_parse_with_topic_tag():
    raw = (
        '{"content": "益生菌成分", "speech_prompt": "平稳",'
        '"source": "script", "reason": "r",'
        '"topic_tag": "成分:益生菌"}'
    )
    out = parse_director_response(raw)
    assert out.topic_tag == "成分:益生菌"


def test_parse_with_cue_hits():
    raw = (
        '{"content": "x", "speech_prompt": "p", "source": "script",'
        '"reason": "r", "cue_hits": ["新西兰原装", "买二送一"]}'
    )
    out = parse_director_response(raw)
    assert out.cue_hits == ["新西兰原装", "买二送一"]


def test_parse_with_qa_flags():
    raw = (
        '{"content": "饭后温水冲服", "speech_prompt": "p", "source": "interaction",'
        '"reason": "r", "is_qa_answer": true, "answered_question": "怎么吃"}'
    )
    out = parse_director_response(raw)
    assert out.is_qa_answer is True
    assert out.answered_question == "怎么吃"


def test_parse_missing_new_fields_uses_defaults():
    raw = '{"content": "x", "speech_prompt": "p", "source": "script", "reason": "r"}'
    out = parse_director_response(raw)
    assert out.topic_tag is None
    assert out.cue_hits == []
    assert out.is_qa_answer is False
    assert out.answered_question is None
