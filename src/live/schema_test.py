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


def test_live_script_from_dict_migrates_text_to_goal():
    """Old segments with 'text' field are migrated to 'goal' on load."""
    data = {
        "meta": {"title": "旧格式", "total_duration": 60},
        "segments": [{"id": "s1", "text": "开场白内容", "duration": 60}],
    }
    script = LiveScript.from_dict(data)
    assert script.segments[0].goal == "开场白内容"
    assert script.segments[0].title == "段落1"


def test_live_script_from_dict_auto_title():
    """Segments without 'title' get auto-generated title '段落N'."""
    data = {
        "meta": {"title": "无标题", "total_duration": 120},
        "segments": [
            {"id": "s1", "goal": "开场", "duration": 60},
            {"id": "s2", "goal": "促单", "duration": 60},
        ],
    }
    script = LiveScript.from_dict(data)
    assert script.segments[0].title == "段落1"
    assert script.segments[1].title == "段落2"
