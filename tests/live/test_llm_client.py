"""Tests for LLMClient prompt building and response parsing."""
from src.live.llm_client import LLMClient, build_prompt
from src.live.schema import Event

SAMPLE_STATE = {
    "segment_id": "qa_open",
    "interruptible": True,
    "keywords": ["提问", "互动"],
    "remaining_seconds": 90.0,
    "finished": False,
    "segment_text": "开放提问环节...",
}

SAMPLE_EVENTS = [
    Event(type="danmaku", user="Alice", text="这个怎么买？", t=30.0),
    Event(type="danmaku", user="Bob", text="主播加油！", t=31.0),
]


def test_build_prompt_contains_segment_id():
    prompt = build_prompt(SAMPLE_STATE, SAMPLE_EVENTS)
    assert "qa_open" in prompt


def test_build_prompt_contains_event_text():
    prompt = build_prompt(SAMPLE_STATE, SAMPLE_EVENTS)
    assert "这个怎么买" in prompt


def test_build_prompt_contains_remaining_seconds():
    prompt = build_prompt(SAMPLE_STATE, SAMPLE_EVENTS)
    assert "90" in prompt


def test_parse_respond_decision():
    raw = '{"action": "respond", "content": "购买链接在直播间左下角！", "interrupt_script": false, "reason": "含购买疑问"}'
    decision = LLMClient.parse_response(raw)
    assert decision.action == "respond"
    assert decision.content == "购买链接在直播间左下角！"
    assert decision.interrupt_script is False


def test_parse_skip_decision():
    raw = '{"action": "skip", "reason": "only cheering, no action needed"}'
    decision = LLMClient.parse_response(raw)
    assert decision.action == "skip"
    assert decision.content is None


def test_parse_malformed_falls_back_to_skip():
    decision = LLMClient.parse_response("not valid json at all")
    assert decision.action == "skip"
    assert "parse error" in decision.reason.lower()
