"""Tests for SessionMemory — layered in-process memory for a live session."""
from __future__ import annotations

import threading

import pytest

from vision_live.session_memory import (
    QAEntry,
    SessionMemory,
    TopicEntry,
    _fingerprint,
    _fmt_age,
)


# ---------------------------------------------------------------------------
# recent_utterances window
# ---------------------------------------------------------------------------


def test_recent_window_drops_old_entries():
    m = SessionMemory(recent_window=3)
    for s in ["a", "b", "c", "d"]:
        m.record_utterance(text=s, topic_tag=None, utterance_id="x",
                           segment_id=None, cue_hits=None)
    rendered = m.render_recent()
    assert "d" in rendered
    assert "c" in rendered
    assert "a" not in rendered


def test_recent_empty_shows_placeholder():
    m = SessionMemory()
    assert "还没说过" in m.render_recent()


# ---------------------------------------------------------------------------
# topic summary
# ---------------------------------------------------------------------------


def test_topic_summary_counts_repeats():
    m = SessionMemory()
    for _ in range(3):
        m.record_utterance(text="x", topic_tag="成分:益生菌",
                           utterance_id="x", segment_id="s1", cue_hits=None)
    out = m.render_topic_summary()
    assert "成分:益生菌" in out
    assert "已讲 3 次" in out


def test_topic_summary_shows_multiple_topics():
    m = SessionMemory()
    m.record_utterance(text="x", topic_tag="成分:益生菌",
                       utterance_id="x", segment_id="s1", cue_hits=None)
    m.record_utterance(text="y", topic_tag="价格优势",
                       utterance_id="y", segment_id="s1", cue_hits=None)
    out = m.render_topic_summary()
    assert "成分:益生菌" in out
    assert "价格优势" in out


def test_topic_summary_empty():
    m = SessionMemory()
    assert m.render_topic_summary() == "(暂无)"


def test_topic_summary_marks_recent_vs_old(monkeypatch):
    m = SessionMemory(topic_lookback_seconds=60)
    # freeze time baseline
    fake_now = [0.0]
    monkeypatch.setattr("vision_live.session_memory.time.monotonic",
                        lambda: m._start_ts + fake_now[0])
    fake_now[0] = 10.0
    m.record_utterance(text="老", topic_tag="老话题",
                       utterance_id="a", segment_id="s1", cue_hits=None)
    fake_now[0] = 200.0
    m.record_utterance(text="新", topic_tag="新话题",
                       utterance_id="b", segment_id="s1", cue_hits=None)
    out = m.render_topic_summary()
    # at t=200, 老话题 age=190s > 60s lookback → [较久]
    assert "老话题" in out and "[较久]" in out
    # 新话题 age=0 → [近期]
    assert "新话题" in out and "[近期]" in out


# ---------------------------------------------------------------------------
# cue status per segment
# ---------------------------------------------------------------------------


def test_cue_status_marks_covered():
    m = SessionMemory()
    m.record_utterance(text="x", topic_tag=None, utterance_id="x",
                       segment_id="s1", cue_hits=["新西兰原装"])
    out = m.render_cue_status("s1", ["新西兰原装", "买二送一"])
    assert "新西兰原装 ✓ 已说" in out
    assert "买二送一 ✗ 未说" in out


def test_cue_status_isolated_per_segment():
    m = SessionMemory()
    m.record_utterance(text="x", topic_tag=None, utterance_id="x",
                       segment_id="s1", cue_hits=["a"])
    m.record_utterance(text="y", topic_tag=None, utterance_id="y",
                       segment_id="s2", cue_hits=["b"])
    assert "a ✓ 已说" in m.render_cue_status("s1", ["a", "b"])
    assert "b ✗ 未说" in m.render_cue_status("s1", ["a", "b"])
    assert "b ✓ 已说" in m.render_cue_status("s2", ["a", "b"])


def test_cue_status_empty_cues_returns_blank():
    m = SessionMemory()
    assert m.render_cue_status("s1", []) == ""


# ---------------------------------------------------------------------------
# QA log
# ---------------------------------------------------------------------------


def test_qa_recorded_and_rendered():
    m = SessionMemory()
    m.record_qa("这个怎么吃", "饭后温水冲服")
    out = m.render_recent_qa()
    assert "怎么吃" in out
    assert "温水冲服" in out


def test_qa_empty():
    m = SessionMemory()
    assert m.render_recent_qa() == "(暂无)"


def test_qa_lookback_window(monkeypatch):
    m = SessionMemory(qa_lookback_seconds=60)
    fake_now = [0.0]
    monkeypatch.setattr("vision_live.session_memory.time.monotonic",
                        lambda: m._start_ts + fake_now[0])
    fake_now[0] = 10.0
    m.record_qa("怎么吃", "饭后温水冲服")
    fake_now[0] = 200.0   # 190s later, outside 60s window
    assert m.is_question_answered("怎么吃") is None
    # render also filters out old QA
    out = m.render_recent_qa()
    assert out == "(暂无)"


def test_qa_within_window_hits():
    m = SessionMemory(qa_lookback_seconds=600)
    m.record_qa("这个怎么吃", "饭后温水冲服")
    hit = m.is_question_answered("怎么吃啊")   # paraphrase
    assert hit is not None
    assert hit.answer == "饭后温水冲服"


def test_qa_fifo_capacity():
    m = SessionMemory(qa_max_entries=3)
    for i in range(5):
        m.record_qa(f"q{i}", f"a{i}")
    # deque should keep last 3
    assert len(m._qa) == 3


# ---------------------------------------------------------------------------
# fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_matches_paraphrase():
    assert _fingerprint("这个怎么吃") == _fingerprint("怎么吃啊")


def test_fingerprint_distinguishes_different_questions():
    assert _fingerprint("多大可以吃") != _fingerprint("怎么吃")


def test_fingerprint_ignores_case_and_whitespace():
    assert _fingerprint("How TO eat") == _fingerprint("how to eat")


# ---------------------------------------------------------------------------
# _fmt_age
# ---------------------------------------------------------------------------


def test_fmt_age_seconds_minutes_hours():
    assert _fmt_age(30) == "30秒"
    assert _fmt_age(120) == "2分"
    assert _fmt_age(3700) == "1.0时"


# ---------------------------------------------------------------------------
# thread safety
# ---------------------------------------------------------------------------


def test_thread_safety_concurrent_writes():
    m = SessionMemory(recent_window=100)

    def worker(i: int) -> None:
        for j in range(50):
            m.record_utterance(text=f"u{i}-{j}", topic_tag=f"t{i}",
                               utterance_id=f"id-{i}-{j}", segment_id="s1",
                               cue_hits=None)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(m._recent) == 100
    # all 200 writes landed in topics
    assert len(m._topics) == 200


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------


def test_topic_entry_fields():
    entry = TopicEntry(tag="x", ts=1.0, utterance_id="u1")
    assert entry.tag == "x" and entry.ts == 1.0 and entry.utterance_id == "u1"


def test_qa_entry_fields():
    entry = QAEntry(question_fingerprint="fp", question_raw="Q",
                    ts=1.0, answer="A")
    assert entry.answer == "A"
