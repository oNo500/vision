from pathlib import Path
from unittest.mock import patch

from vision_intelligence.video_asr.analyzer import (
    analyze_transcript, _filter_for_style,
)
from vision_intelligence.video_asr.models import (
    RawTranscript, SegmentRecord, StyleProfile,
)


def _seg(text, speaker="host", conf=0.9):
    return SegmentRecord(
        idx=0, start=0, end=1, speaker=speaker,
        text=text, text_normalized=text,
        confidence=conf, chunk_id=0,
    )


def test_filter_keeps_only_high_conf_host():
    segs = [
        _seg("keep me", "host", 0.9),
        _seg("guest speech", "guest", 0.9),
        _seg("low conf", "host", 0.5),
        _seg("unknown", "unknown", 0.9),
    ]
    out = _filter_for_style(segs, min_conf=0.6)
    texts = [s.text for s in out]
    assert texts == ["keep me"]


def test_analyze_returns_summary_and_style(tmp_path):
    raw = RawTranscript(
        video_id="abc", source="youtube",
        url="u", title="t", uploader="u", duration_sec=10,
        asr_model="m", asr_version="v", processed_at="t",
        bgm_removed=True,
        segments=[_seg("家人们晚上好", "host", 0.95)],
    )
    fake_style_dict = {
        "top_phrases": [], "catchphrases": [], "opening_hooks": [],
        "cta_patterns": [], "transition_patterns": [], "tone_tags": [],
    }
    with patch("vision_intelligence.video_asr.analyzer._call_summary") as m_sum, \
         patch("vision_intelligence.video_asr.analyzer._call_style") as m_style:
        m_sum.return_value = ("# summary\nhi", {"input_tokens": 100, "output_tokens": 50})
        m_style.return_value = (fake_style_dict,
                                {"input_tokens": 100, "output_tokens": 50})
        result = analyze_transcript(
            raw, project="p", location="us-central1",
            model="gemini-2.5-flash", min_confidence=0.6,
        )
    assert result.summary_md.startswith("# summary")
    assert isinstance(result.style, StyleProfile)
    assert result.style.video_id == "abc"
