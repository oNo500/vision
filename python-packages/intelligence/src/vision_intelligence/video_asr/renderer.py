"""Render raw.json -> transcript.md + transcript.srt."""
from __future__ import annotations

from vision_intelligence.video_asr.models import RawTranscript, Speaker

_LABEL: dict[Speaker, str] = {
    "host": "主播", "guest": "嘉宾", "other": "其他", "unknown": "未知",
}


def format_srt_timestamp(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_markdown(raw: RawTranscript) -> str:
    lines: list[str] = [
        f"# {raw.title or raw.video_id}",
        "",
        f"**来源**: {raw.source} · {raw.uploader or '-'} · {raw.duration_sec or '-'}s",
        f"**处理时间**: {raw.processed_at}",
        f"**模型**: {raw.asr_model}",
        "",
        "---",
        "",
    ]
    for s in raw.segments:
        ts = format_srt_timestamp(s.start).split(",")[0]
        lines.append(f"**[{ts}] {_LABEL[s.speaker]}**: {s.text}")
        lines.append("")
    return "\n".join(lines)


def render_srt(raw: RawTranscript) -> str:
    blocks: list[str] = []
    for i, s in enumerate(raw.segments, start=1):
        blocks.append(
            f"{i}\n"
            f"{format_srt_timestamp(s.start)} --> {format_srt_timestamp(s.end)}\n"
            f"[{_LABEL[s.speaker]}] {s.text}\n"
        )
    return "\n".join(blocks)
