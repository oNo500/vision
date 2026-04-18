from vision_intelligence.video_asr.renderer import (
    render_markdown, render_srt, format_srt_timestamp,
)
from vision_intelligence.video_asr.models import RawTranscript, SegmentRecord


def _raw(segments):
    return RawTranscript(
        video_id="abc", source="youtube",
        url="https://www.youtube.com/watch?v=abc",
        title="示例", uploader="Up", duration_sec=100.0,
        asr_model="gemini-2.5-flash", asr_version="v1",
        processed_at="2026-04-18T00:00:00+08:00",
        bgm_removed=True, segments=segments,
    )


def test_format_srt_timestamp():
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.123) == "00:01:05,123"
    assert format_srt_timestamp(3661.5) == "01:01:01,500"


def test_render_markdown_contains_header_and_speakers():
    segs = [
        SegmentRecord(idx=0, start=0.52, end=4.0, speaker="host",
                      text="家人们晚上好", text_normalized="",
                      confidence=0.95, chunk_id=0),
        SegmentRecord(idx=1, start=5.0, end=8.0, speaker="guest",
                      text="谢谢", text_normalized="", confidence=0.9, chunk_id=0),
    ]
    md = render_markdown(_raw(segs))
    assert "# 示例" in md
    assert "主播" in md and "嘉宾" in md
    assert "家人们晚上好" in md


def test_render_srt_numbered_blocks():
    segs = [
        SegmentRecord(idx=0, start=0.0, end=2.0, speaker="host",
                      text="A", text_normalized="", confidence=1.0, chunk_id=0),
    ]
    srt = render_srt(_raw(segs))
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,000\n[主播] A\n")
