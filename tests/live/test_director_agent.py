"""Tests for DirectorAgent."""
from scripts.live.director_agent import build_director_prompt
from scripts.live.schema import DirectorOutput, Event


SCRIPT_STATE = {
    "segment_id": "opening",
    "segment_text": "大家好，欢迎来到直播间！今天带来超能面膜。",
    "interruptible": True,
    "keywords": ["欢迎", "开场"],
    "remaining_seconds": 80.0,
    "finished": False,
    "must_say": False,
}

KNOWLEDGE_CTX = "【产品】超能面膜 — 28天焕新\n【卖点】\n  - 纯植物萃取"

EVENTS = [
    Event(type="danmaku", user="Alice", text="好期待", t=5.0),
    Event(type="gift", user="Bob", gift="小心心", value=1, t=10.0),
]


def test_build_prompt_contains_segment_text():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="")
    assert "大家好" in prompt


def test_build_prompt_contains_knowledge():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="")
    assert "超能面膜" in prompt


def test_build_prompt_contains_events():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="")
    assert "Alice" in prompt
    assert "好期待" in prompt


def test_build_prompt_contains_last_said():
    prompt = build_director_prompt(SCRIPT_STATE, KNOWLEDGE_CTX, EVENTS, last_said="欢迎大家来到直播间")
    assert "欢迎大家来到直播间" in prompt


def test_director_output_defaults():
    out = DirectorOutput(content="你好", speech_prompt="热情")
    assert out.source == "script"
    assert out.reason == ""
