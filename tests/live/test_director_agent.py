"""Tests for DirectorAgent."""
import queue
import time
from unittest.mock import MagicMock

from scripts.live.director_agent import (
    DirectorAgent,
    build_director_prompt,
    parse_director_response,
)
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


def test_parse_valid_response():
    raw = '{"content": "欢迎大家！", "speech_prompt": "热情欢快", "source": "script", "reason": "开场"}'
    out = parse_director_response(raw)
    assert out.content == "欢迎大家！"
    assert out.speech_prompt == "热情欢快"
    assert out.source == "script"


def test_parse_missing_content_returns_empty():
    raw = '{"speech_prompt": "热情", "source": "script", "reason": "test"}'
    out = parse_director_response(raw)
    assert out.content == ""


def test_parse_invalid_json_returns_empty():
    out = parse_director_response("not json at all")
    assert out.content == ""
    assert "parse error" in out.reason


def test_parse_strips_markdown_fence():
    raw = '```json\n{"content": "好的", "speech_prompt": "平稳", "source": "script", "reason": ""}\n```'
    out = parse_director_response(raw)
    assert out.content == "好的"


def test_director_enqueues_content():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = False
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"content": "大家好！", "speech_prompt": "热情", "source": "script", "reason": "test"}'

    script_state = {
        "segment_id": "opening", "segment_text": "欢迎", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    }

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="【产品】测试面膜",
        llm_generate_fn=mock_llm.generate,
    )

    director._fire(script_state, recent_events=[])
    assert not tts_q.empty()
    text, prompt = tts_q.get_nowait()
    assert text == "大家好！"
    assert prompt == "热情"


def test_director_pregens_while_speaking():
    """Director should pre-generate next utterance even while TTS is speaking (queue lookahead)."""
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = True   # TTS currently speaking
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"content": "下一句", "speech_prompt": "平稳", "source": "script", "reason": ""}'

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="",
        llm_generate_fn=mock_llm.generate,
    )

    script_state = {
        "segment_id": "opening", "segment_text": "", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    }
    director._fire(script_state, recent_events=[])
    # Should still call LLM and enqueue (pre-generation while speaking)
    mock_llm.generate.assert_called_once()
    assert not tts_q.empty()


def test_director_skips_empty_content():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = False
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "not valid json"  # parse_director_response returns content=""

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="",
        llm_generate_fn=mock_llm.generate,
    )
    script_state = {
        "segment_id": "opening", "segment_text": "", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    }
    director._fire(script_state, recent_events=[])
    assert tts_q.empty()  # empty content is not enqueued


def test_director_stops_cleanly():
    tts_q: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mock_tts = MagicMock()
    mock_tts.is_speaking = False
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"content": "测试", "speech_prompt": "平稳", "source": "script", "reason": ""}'

    get_state = MagicMock(return_value={
        "segment_id": "opening", "segment_text": "测试", "interruptible": True,
        "keywords": [], "remaining_seconds": 60.0, "finished": False, "must_say": False,
    })

    director = DirectorAgent(
        tts_queue=tts_q,
        tts_player=mock_tts,
        knowledge_ctx="",
        llm_generate_fn=mock_llm.generate,
    )
    director.start(get_state_fn=get_state, get_events_fn=lambda: [])
    time.sleep(0.2)
    director.stop()   # must not hang
