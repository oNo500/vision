"""Gemini 2.5 Flash ASR via google-genai (Vertex AI, ADC)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from vision_intelligence.video_asr.gemini_lock import gemini_lock
from vision_intelligence.video_asr.models import (
    ChunkTranscript, SegmentRecord, Speaker,
)


class _SegmentModel(BaseModel):
    start: float
    end: float
    speaker: Literal["host", "guest", "other", "unknown"]
    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class _ResponseModel(BaseModel):
    segments: list[_SegmentModel]


def _load_prompt() -> str:
    here = Path(__file__).parent.parent / "prompts" / "transcribe.md"
    return here.read_text(encoding="utf-8")


def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    msg = str(exc)
    return (
        "RESOURCE_EXHAUSTED" in msg
        or "429" in msg
        or "SSL" in msg
        or "EOF" in msg
        or "ConnectError" in name
        or "TimeoutError" in name
        or "ServiceUnavailable" in name
        or "JSONDecodeError" in name  # truncated response — retry may get full output
    )


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=2, min=15, max=180),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def _call_gemini_audio(
    *, client, model: str, audio_bytes: bytes, prompt: str,
) -> tuple[_ResponseModel, dict]:
    """Return (parsed response, usage dict). Wrapped for test mocking + retry."""
    import json
    from google.genai import types as gtypes
    with gemini_lock():
        resp = client.models.generate_content(
            model=model,
            contents=[
                prompt,
                gtypes.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
            ],
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        usage = {
            "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) or 0,
        }
        text = resp.text or ""
        if not text.strip():
            raise ValueError(f"Gemini returned empty response (finish_reason={getattr(resp, 'finish_reason', 'unknown')})")
        data = json.loads(text)
        # Gemini sometimes returns a bare list instead of {"segments": [...]}
        if isinstance(data, list):
            data = {"segments": data}
    parsed = _ResponseModel.model_validate(data)
    return parsed, usage


class GeminiTranscriber:
    name = "gemini"

    def __init__(self, *, model: str, project: str, location: str) -> None:
        self.model = model
        self.project = project
        self.location = location
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(
                vertexai=True, project=self.project, location=self.location,
            )
        return self._client

    def transcribe_chunk(
        self, audio_path: Path, *, chunk_id: int, start_offset: float,
    ) -> ChunkTranscript:
        audio_bytes = audio_path.read_bytes()
        client = self._get_client()
        prompt = _load_prompt()
        parsed, usage = _call_gemini_audio(
            client=client, model=self.model,
            audio_bytes=audio_bytes, prompt=prompt,
        )
        segments = [
            SegmentRecord(
                idx=i,
                start=s.start + start_offset,
                end=s.end + start_offset,
                speaker=s.speaker,
                text=s.text,
                text_normalized="",  # filled by merger/storage later
                confidence=s.confidence,
                chunk_id=chunk_id,
            )
            for i, s in enumerate(parsed.segments)
        ]
        ct = ChunkTranscript(chunk_id=chunk_id, start_offset=start_offset,
                             segments=segments)
        return ct

    def last_usage_for_chunk(self) -> dict:
        """Placeholder -- pipeline should capture via wrapped call instead."""
        return {}
