"""FunASR paraformer-zh-long transcriber — local offline fallback."""
from __future__ import annotations

from pathlib import Path

import structlog

from vision_intelligence.video_asr.models import ChunkTranscript, SegmentRecord

log = structlog.get_logger()


class FunasrTranscriber:
    name = "funasr"

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            log.info("funasr_model_loading")
            from funasr import AutoModel
            self._model = AutoModel(
                model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
                disable_update=True,
            )
            log.info("funasr_model_ready")
        return self._model

    def transcribe_chunk(
        self, audio_path: Path, *, chunk_id: int, start_offset: float,
    ) -> ChunkTranscript:
        model = self._get_model()
        results = model.generate(
            input=str(audio_path), batch_size_s=300, sentence_timestamp=True,
        )
        segments = []
        idx = 0
        for res in results:
            for item in res.get("sentence_info", []):
                start = item["start"] / 1000.0 + start_offset
                end = item["end"] / 1000.0 + start_offset
                text = item.get("text", "").strip()
                if not text:
                    continue
                segments.append(SegmentRecord(
                    idx=idx,
                    start=start,
                    end=end,
                    speaker="unknown",
                    text=text,
                    text_normalized="",
                    confidence=0.95,
                    chunk_id=chunk_id,
                    asr_engine="funasr-paraformer-large",
                ))
                idx += 1
        return ChunkTranscript(
            chunk_id=chunk_id,
            start_offset=start_offset,
            segments=segments,
            asr_engine="funasr-paraformer-large",
        )
