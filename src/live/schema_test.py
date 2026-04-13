"""Tests for ScriptSegment and LiveScript schema."""
from src.live.schema import ScriptSegment, LiveScript


def test_script_segment_defaults():
    seg = ScriptSegment(id="s1", title="开场", goal="欢迎观众", duration=300)
    assert seg.cue == []
    assert seg.must_say is False
    assert seg.keywords == []


def test_script_segment_with_cue():
    seg = ScriptSegment(
        id="s1",
        title="促单",
        goal="引导下单",
        duration=300,
        cue=["直播间专属价299", "库存不多了"],
        must_say=True,
        keywords=["299", "库存"],
    )
    assert seg.must_say is True
    assert len(seg.cue) == 2


def test_live_script_from_dict():
    data = {
        "meta": {"title": "测试直播", "total_duration": 600},
        "segments": [
            {
                "id": "s1",
                "title": "开场",
                "goal": "欢迎观众",
                "duration": 300,
                "cue": ["欢迎来到直播间"],
                "must_say": False,
                "keywords": ["欢迎"],
            }
        ],
    }
    script = LiveScript.from_dict(data)
    assert script.title == "测试直播"
    assert len(script.segments) == 1
    seg = script.segments[0]
    assert seg.title == "开场"
    assert seg.goal == "欢迎观众"
    assert seg.cue == ["欢迎来到直播间"]
    assert seg.must_say is False


def test_script_segment_no_text_field():
    """ScriptSegment must not have a 'text' attribute."""
    seg = ScriptSegment(id="s1", title="开场", goal="欢迎", duration=60)
    assert not hasattr(seg, "text")


def test_script_segment_no_interruptible_field():
    """ScriptSegment must not have an 'interruptible' attribute."""
    seg = ScriptSegment(id="s1", title="开场", goal="欢迎", duration=60)
    assert not hasattr(seg, "interruptible")
