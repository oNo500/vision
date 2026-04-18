from vision_intelligence.video_asr.sources.yaml_loader import load_sources


def test_load_14_videos():
    videos = load_sources("config/video_asr/sources.yaml")
    assert len(videos) == 14
    ids = {v.video_id for v in videos}
    assert "0y3O90vyKNo" in ids
    assert "BV1at4y1h7X4" in ids
