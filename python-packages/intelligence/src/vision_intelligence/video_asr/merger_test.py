from vision_intelligence.video_asr.merger import (
    merge_chunks, _is_near_duplicate, _sanitize_timestamps,
)
from vision_intelligence.video_asr.models import ChunkTranscript, SegmentRecord


def _seg(idx, start, end, text, speaker="host", conf=0.9, chunk_id=0):
    return SegmentRecord(
        idx=idx, start=start, end=end, speaker=speaker,
        text=text, text_normalized=text, confidence=conf, chunk_id=chunk_id,
    )


def test_is_near_duplicate_yes():
    assert _is_near_duplicate("家人们晚上好呀", "家人们晚上好呀！") is True


def test_is_near_duplicate_no():
    assert _is_near_duplicate("今天讲A产品", "今天讲B产品") is False


def test_sanitize_swap_start_end():
    seg = _seg(0, 5.0, 3.0, "x")
    out = _sanitize_timestamps([seg])
    assert out[0].start == 3.0 and out[0].end == 5.0


def test_sanitize_drops_empty():
    segs = [_seg(0, 0, 1, ""), _seg(1, 1, 2, "真的好")]
    out = _sanitize_timestamps(segs)
    assert len(out) == 1
    assert out[0].text == "真的好"


def test_merge_drops_overlap_duplicates():
    # Chunk 0: 0-20 (end offset 1200 if chunk 1 starts at 1190)
    c0 = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=[
        _seg(0, 1185.0, 1188.0, "结尾话术", chunk_id=0),
    ])
    c1 = ChunkTranscript(chunk_id=1, start_offset=1190.0, segments=[
        _seg(0, 1186.0, 1188.5, "结尾话术！", chunk_id=1),
        _seg(1, 1195.0, 1200.0, "下一段", chunk_id=1),
    ])
    merged = merge_chunks([c0, c1])
    # Near-duplicate "结尾话术" should be collapsed
    texts = [s.text for s in merged.segments]
    assert texts.count("结尾话术") + texts.count("结尾话术！") == 1
    assert "下一段" in texts


def test_merge_converts_traditional_to_simplified():
    c = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=[
        _seg(0, 0, 1, "這個實體"),
    ])
    merged = merge_chunks([c])
    assert "这个实体" in merged.segments[0].text


def test_merge_normalizes_punctuation():
    c = ChunkTranscript(chunk_id=0, start_offset=0.0, segments=[
        _seg(0, 0, 1, "家人们好,真的不错!"),
    ])
    merged = merge_chunks([c])
    assert merged.segments[0].text == "家人们好，真的不错！"
