"""Tests for RAG integration in DirectorAgent."""
from __future__ import annotations

import queue
from unittest.mock import MagicMock

from vision_live.director_agent import DirectorAgent, build_director_prompt
from vision_live.rag import TalkPoint


def _state(cue: list[str] | None = None) -> dict:
    return {
        "segment_id": "s1",
        "title": "产品介绍",
        "goal": "讲益生菌成分",
        "cue": cue or [],
        "must_say": False,
        "keywords": [],
        "remaining_seconds": 300,
    }


# ---------------------------------------------------------------------------
# build_director_prompt renders RAG section
# ---------------------------------------------------------------------------


def test_prompt_renders_talk_points_section():
    points = [
        TalkPoint(id="1", text="这款益生菌每条含 2000 亿活菌",
                  source="scripts/opening.md", category="scripts", chunk_index=0),
        TalkPoint(id="2", text="纯植物萃取,宝宝可以放心吃",
                  source="product_manual/spec.md", category="product_manual",
                  chunk_index=3),
    ]
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], talk_points=points,
    )
    assert "相关话术参考" in prompt
    assert "2000 亿活菌" in prompt
    assert "scripts/opening.md" in prompt
    assert "product_manual/spec.md" in prompt


def test_prompt_without_talk_points_has_no_rag_section():
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], talk_points=None,
    )
    assert "相关话术参考" not in prompt


def test_prompt_empty_talk_points_list_has_no_rag_section():
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], talk_points=[],
    )
    assert "相关话术参考" not in prompt


def test_prompt_talk_points_truncated_to_200_chars():
    long_text = "x" * 500
    points = [TalkPoint(id="1", text=long_text, source="s.md",
                        category="scripts", chunk_index=0)]
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], talk_points=points,
    )
    # only 200 chars of x should appear
    assert "x" * 200 in prompt
    assert "x" * 300 not in prompt


def test_prompt_talk_points_capped_at_5():
    points = [
        TalkPoint(id=str(i), text=f"point-{i}", source=f"s{i}.md",
                  category="scripts", chunk_index=i)
        for i in range(10)
    ]
    prompt = build_director_prompt(
        script_state=_state(), knowledge_ctx="ctx",
        recent_events=[], talk_points=points,
    )
    assert "point-0" in prompt
    assert "point-4" in prompt
    assert "point-5" not in prompt


# ---------------------------------------------------------------------------
# DirectorAgent._fire queries RAG and threads results through
# ---------------------------------------------------------------------------


class _StubRAG:
    def __init__(self, points: list[TalkPoint] | Exception):
        self._points = points
        self.last_call: dict | None = None

    def query(self, segment_goal, recent_danmaku, k=5):
        self.last_call = {"goal": segment_goal, "danmaku": list(recent_danmaku), "k": k}
        if isinstance(self._points, Exception):
            raise self._points
        return self._points


def _director(rag=None, on_rag_miss=None, llm_return='{"content": "x", "speech_prompt": "p", "source": "script", "reason": ""}'):
    tts_q = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = False
    mock_llm = MagicMock(return_value=llm_return)

    agent = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="ctx",
        llm_generate_fn=mock_llm,
        rag=rag,
        on_rag_miss=on_rag_miss,
    )
    return agent, mock_llm, mock_tts


def test_fire_calls_rag_with_goal_and_danmaku():
    from vision_live.schema import Event
    rag = _StubRAG(points=[TalkPoint(id="1", text="t", source="s.md",
                                     category="scripts", chunk_index=0)])
    agent, mock_llm, _ = _director(rag=rag)
    events = [Event(type="danmaku", user="U", text="怎么买", t=0)]

    agent._fire(_state(), events)

    assert rag.last_call is not None
    assert rag.last_call["goal"] == "讲益生菌成分"
    assert rag.last_call["danmaku"] == ["怎么买"]


def test_fire_only_uses_danmaku_events_not_gifts():
    from vision_live.schema import Event
    rag = _StubRAG(points=[])
    agent, _, _ = _director(rag=rag, on_rag_miss=lambda: None)
    events = [
        Event(type="gift", user="A", gift="rocket", value=500, t=0),
        Event(type="danmaku", user="B", text="hello", t=0),
    ]
    agent._fire(_state(), events)
    assert rag.last_call["danmaku"] == ["hello"]


def test_fire_passes_talk_points_to_llm_via_prompt():
    from vision_live.schema import Event
    rag = _StubRAG(points=[TalkPoint(id="1", text="益生菌 2000 亿",
                                     source="s.md", category="scripts",
                                     chunk_index=0)])
    agent, mock_llm, _ = _director(rag=rag)
    agent._fire(_state(), [])

    prompt_arg = mock_llm.call_args[0][0]
    assert "益生菌 2000 亿" in prompt_arg


def test_fire_degrades_when_rag_raises():
    rag = _StubRAG(points=RuntimeError("boom"))
    agent, mock_llm, mock_tts = _director(rag=rag)
    # must not raise — degrade silently and still call LLM
    agent._fire(_state(), [])
    mock_llm.assert_called_once()
    mock_tts.put.assert_called_once()


def test_fire_calls_on_rag_miss_when_no_points():
    rag = _StubRAG(points=[])
    miss_calls = []
    agent, _, _ = _director(rag=rag, on_rag_miss=lambda: miss_calls.append(True))
    agent._fire(_state(), [])
    assert miss_calls == [True]


def test_fire_does_not_call_on_rag_miss_when_hits_found():
    rag = _StubRAG(points=[TalkPoint(id="1", text="x", source="s.md",
                                     category="scripts", chunk_index=0)])
    miss_calls = []
    agent, _, _ = _director(rag=rag, on_rag_miss=lambda: miss_calls.append(True))
    agent._fire(_state(), [])
    assert miss_calls == []


def test_fire_with_rag_none_skips_query_and_miss():
    miss_calls = []
    agent, mock_llm, _ = _director(rag=None, on_rag_miss=lambda: miss_calls.append(True))
    agent._fire(_state(), [])
    mock_llm.assert_called_once()
    assert miss_calls == []
