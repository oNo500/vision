"""Tests for schema dataclasses."""
from scripts.live.schema import Decision, Event, LiveScript, ScriptSegment


def test_event_creation():
    e = Event(type="danmaku", user="Alice", text="hello", t=10.0)
    assert e.type == "danmaku"
    assert e.user == "Alice"
    assert e.text == "hello"
    assert e.t == 10.0


def test_event_gift_defaults():
    e = Event(type="gift", user="Bob", gift="rocket", value=500, t=5.0)
    assert e.type == "gift"
    assert e.gift == "rocket"
    assert e.value == 500
    assert e.text is None


def test_script_segment_defaults():
    seg = ScriptSegment(id="opening", duration=120, text="Hello everyone!")
    assert seg.interruptible is True
    assert seg.keywords == []


def test_script_segment_not_interruptible():
    seg = ScriptSegment(id="core", duration=300, text="Product details...", interruptible=False)
    assert seg.interruptible is False


def test_live_script_from_dict():
    data = {
        "meta": {"title": "Test Live", "total_duration": 600},
        "segments": [
            {"id": "opening", "duration": 60, "text": "Hello!", "interruptible": True, "keywords": ["welcome"]},
            {"id": "core", "duration": 300, "text": "Core content.", "interruptible": False},
        ],
    }
    script = LiveScript.from_dict(data)
    assert script.title == "Test Live"
    assert len(script.segments) == 2
    assert script.segments[0].id == "opening"
    assert script.segments[1].keywords == []


def test_decision_defaults():
    d = Decision(action="skip")
    assert d.content is None
    assert d.interrupt_script is False
    assert d.reason == ""


def test_decision_respond():
    d = Decision(action="respond", content="Thanks!", interrupt_script=True, reason="gift received")
    assert d.action == "respond"
    assert d.content == "Thanks!"
