from vision_intelligence.video_asr.sources.registry import get_source


def test_registry_routes_youtube():
    src = get_source("https://www.youtube.com/watch?v=abc")
    assert src.name == "yt_dlp"


def test_registry_routes_bilibili():
    src = get_source("https://www.bilibili.com/video/BVxxx")
    assert src.name == "yt_dlp"


def test_registry_unknown_raises():
    import pytest
    with pytest.raises(ValueError):
        get_source("https://example.com/video")
