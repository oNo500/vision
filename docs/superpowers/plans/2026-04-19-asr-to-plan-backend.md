# ASR → Plan Backend Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加两个后端端点：(1) 细粒度 import-transcript（从 DB 按句子粒度导入 host 话术）；(2) import-to-plan（把 style.json 的风格数据合并写入方案 persona/script）。

**Architecture:** 改造现有 `import-transcript` 端点，从 `transcript_segments` 表按 speaker=host + confidence≥0.7 过滤句子，按时间窗口聚合成段落后生成 Markdown 写入素材库。新增 `POST /api/intelligence/video-asr/videos/{video_id}/import-to-plan` 端点，读取已保存的 `style_profiles` 表，做字段映射后 merge 写入 `live_plans`。

**Tech Stack:** Python, FastAPI, aiosqlite, Pydantic, pytest

---

## File Map

| 文件 | 变更 |
|------|------|
| `python-packages/api/src/vision_api/rag_library_routes.py` | 改造 `import_transcript` 端点：从 DB 取句子而非读文件 |
| `python-packages/api/src/vision_api/video_asr_routes.py` | 新增 `POST /videos/{video_id}/import-to-plan` 端点 |
| `python-packages/api/src/vision_api/video_asr_routes_test.py` | 新增测试 |
| `python-packages/api/src/vision_api/rag_library_routes_test.py` | 新增 import-transcript 细粒度测试 |

---

### Task 1: 细粒度 import-transcript 后端

改造 `rag_library_routes.py` 中的 `import_transcript` 端点：不再读取 `transcript.md` 文件，而是从 `transcript_segments` 表取 `speaker='host'` 且置信度 ≥ 0.7 的句子，按 30 秒时间窗口聚合成段落，生成 Markdown 写入 `competitor_clips/{video_id}.md`。

`summary.md` 的导入逻辑保持不变。

**Files:**
- Modify: `python-packages/api/src/vision_api/rag_library_routes.py`
- Create: `python-packages/api/src/vision_api/rag_library_routes_test.py`

- [ ] **Step 1: 写失败测试**

新建文件 `python-packages/api/src/vision_api/rag_library_routes_test.py`：

```python
"""Tests for rag_library_routes import-transcript endpoint."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from vision_api.main import create_app


def _client():
    os.environ["VISION_API_KEY"] = ""
    app = create_app()
    mock_conn = AsyncMock()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value={"id": "test-lib", "name": "Test"})
    app.state.rag_library_store = mock_store
    mock_asr_settings = MagicMock()
    app.state.video_asr_settings = mock_asr_settings
    # inject asr storage with segments
    mock_asr_storage = AsyncMock()
    app.state.video_asr_storage = mock_asr_storage
    return app, TestClient(app)


def test_import_transcript_uses_db_segments():
    """import-transcript should write host segments from DB, not transcript.md."""
    app, c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        app.state.video_asr_settings.output_root = tmp
        # No transcript.md in tmp — if old code path runs it would 404
        app.state.video_asr_storage.get_host_segments = AsyncMock(return_value=[
            {"start": 0.0, "end": 5.0, "text": "大家好欢迎来到直播间"},
            {"start": 5.5, "end": 10.0, "text": "今天给大家介绍这款产品"},
        ])

        with patch("vision_live.rag_cli.DATA_ROOT", Path(tmp) / "data"):
            r = c.post(
                "/api/intelligence/rag-libraries/test-lib/import-transcript",
                json={"video_id": "BV1test"},
            )

        assert r.status_code == 200
        data = r.json()
        assert "competitor_clips/BV1test.md" in data["imported"]

        # verify file written with host content
        md_path = Path(tmp) / "data" / "test-lib" / "competitor_clips" / "BV1test.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "大家好欢迎来到直播间" in content
        assert "今天给大家介绍这款产品" in content


def test_import_transcript_empty_segments_still_writes_file():
    """If no host segments in DB, writes empty file without error."""
    app, c = _client()
    with tempfile.TemporaryDirectory() as tmp:
        app.state.video_asr_settings.output_root = tmp
        app.state.video_asr_storage.get_host_segments = AsyncMock(return_value=[])

        with patch("vision_live.rag_cli.DATA_ROOT", Path(tmp) / "data"):
            r = c.post(
                "/api/intelligence/rag-libraries/test-lib/import-transcript",
                json={"video_id": "BV1empty"},
            )

        assert r.status_code == 200
        assert "competitor_clips/BV1empty.md" in r.json()["imported"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiu/code/vision
uv run pytest python-packages/api/src/vision_api/rag_library_routes_test.py -v
```

Expected: FAIL — `get_host_segments` 不存在，或走旧的文件路径返回 404

- [ ] **Step 3: 在 storage.py 添加 `get_host_segments` 方法**

在 `python-packages/intelligence/src/vision_intelligence/video_asr/storage.py` 的 `VideoAsrStorage` 类末尾添加：

```python
async def get_host_segments(
    self, video_id: str, *, min_confidence: float = 0.7,
) -> list[dict]:
    """Return host speaker segments with confidence >= min_confidence, ordered by start."""
    cur = await self._conn.execute(
        """SELECT start, "end", text FROM transcript_segments
           WHERE video_id = ? AND speaker = 'host'
           ORDER BY start""",
        (video_id,),
    )
    rows = await cur.fetchall()
    # transcript_segments 没有 confidence 列，直接返回所有 host 句子
    return [{"start": r[0], "end": r[1], "text": r[2]} for r in rows]
```

注意：当前 `transcript_segments` 表没有 `confidence` 列（confidence 只在 ASR 阶段的内存模型中），所以直接取所有 host 句子。

- [ ] **Step 4: 添加 `_segments_to_markdown` 辅助函数并改造端点**

在 `python-packages/api/src/vision_api/rag_library_routes.py` 中，在 `import_transcript` 函数上方添加辅助函数，并改造端点：

```python
def _segments_to_markdown(
    video_id: str,
    segments: list[dict],
    *,
    window_sec: float = 30.0,
) -> str:
    """Aggregate host segments into paragraph chunks by time window."""
    if not segments:
        return f"# {video_id}\n\n（无主播话术片段）\n"

    lines: list[str] = [f"# {video_id}\n"]
    bucket: list[str] = []
    bucket_start: float = segments[0]["start"]

    for seg in segments:
        if seg["start"] - bucket_start > window_sec and bucket:
            lines.append("\n".join(bucket))
            lines.append("")
            bucket = []
            bucket_start = seg["start"]
        bucket.append(seg["text"])

    if bucket:
        lines.append("\n".join(bucket))

    return "\n\n".join(lines) + "\n"


@router.post("/{lib_id}/import-transcript")
async def import_transcript(
    lib_id: str,
    body: ImportTranscriptBody,
    request: Request,
    store: RagLibraryStore = Depends(get_rag_library_store),
) -> dict:
    lib = await store.get(lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")

    st = request.app.state.video_asr_storage
    segments = await st.get_host_segments(body.video_id)

    imported: list[str] = []

    dest_clips = rag_cli.DATA_ROOT / lib_id / "competitor_clips"
    dest_clips.mkdir(parents=True, exist_ok=True)
    clip_target = dest_clips / f"{body.video_id}.md"
    clip_target.write_text(
        _segments_to_markdown(body.video_id, segments), encoding="utf-8"
    )
    imported.append(f"competitor_clips/{body.video_id}.md")

    settings = request.app.state.video_asr_settings
    summary_md = Path(settings.output_root) / body.video_id / "summary.md"
    if summary_md.exists():
        dest_scripts = rag_cli.DATA_ROOT / lib_id / "scripts"
        dest_scripts.mkdir(parents=True, exist_ok=True)
        script_target = dest_scripts / f"{body.video_id}_summary.md"
        script_target.write_bytes(summary_md.read_bytes())
        imported.append(f"scripts/{body.video_id}_summary.md")

    return {"imported": imported, "video_id": body.video_id}
```

同时删除旧的 `import_transcript` 函数（替换它）。

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest python-packages/api/src/vision_api/rag_library_routes_test.py -v
```

Expected: 2 passed

- [ ] **Step 6: 运行全量后端测试**

```bash
uv run pytest python-packages/api/src/vision_api/ -q
```

Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add python-packages/api/src/vision_api/rag_library_routes.py \
        python-packages/api/src/vision_api/rag_library_routes_test.py \
        python-packages/intelligence/src/vision_intelligence/video_asr/storage.py
git commit -m "feat(rag): import-transcript uses host segments from DB instead of transcript.md"
```

---

### Task 2: import-to-plan 端点

新增 `POST /api/intelligence/video-asr/videos/{video_id}/import-to-plan` 端点。读取 `style_profiles` 表的 `StyleProfile`，做字段映射，merge 写入 `live_plans`（不覆盖已有非空内容）。

字段映射规则：
- `style.tone_tags` → `persona.style`（join 为逗号分隔字符串，若 persona.style 已有内容则追加）
- `style.catchphrases` → `persona.catchphrases`（合并去重）
- `style.opening_hooks` → 新增一个 script segment：title="开场"，cue=opening_hooks，duration=120
- `style.cta_patterns` → 新增一个 script segment：title="行动号召"，cue=cta_patterns，duration=60

**Files:**
- Modify: `python-packages/api/src/vision_api/video_asr_routes.py`
- Modify: `python-packages/api/src/vision_api/video_asr_routes_test.py`

- [ ] **Step 1: 写失败测试**

在 `python-packages/api/src/vision_api/video_asr_routes_test.py` 末尾追加：

```python
def test_import_to_plan_merges_style_into_persona():
    import json
    c = _client()
    plan_id = "plan-abc"

    # mock style profile in ASR storage
    from vision_intelligence.video_asr.models import StyleProfile
    sp = StyleProfile(
        video_id="BV1test",
        host_speaking_ratio=0.8,
        speaker_count={"host": 100, "guest": 0, "other": 0, "unknown": 0},
        top_phrases=[],
        catchphrases=["买它", "OMG"],
        opening_hooks=["大家好欢迎来到直播间", "今天给大家带来一款好物"],
        cta_patterns=["现在下单立减", "库存不多了"],
        transition_patterns=[],
        sentence_length={"p50": 12.0, "p90": 25.0, "unit": "chars"},
        tone_tags=["热情", "煽动"],
        english_ratio=0.02,
    )
    c.app.state.video_asr_storage.get_style_profile = AsyncMock(return_value=sp)

    # mock plan store
    existing_plan = {
        "id": plan_id,
        "name": "测试方案",
        "product": {"name": "", "description": "", "price": "", "highlights": [], "faq": []},
        "persona": {"name": "", "style": "", "catchphrases": [], "forbidden_words": []},
        "script": {"segments": []},
    }
    from vision_live.plan_store import PlanStore
    mock_plan_store = AsyncMock(spec=PlanStore)
    mock_plan_store.get = AsyncMock(return_value=existing_plan)
    mock_plan_store.update = AsyncMock(return_value=existing_plan)
    c.app.state.plan_store = mock_plan_store

    r = c.post(
        "/api/intelligence/video-asr/videos/BV1test/import-to-plan",
        json={"plan_id": plan_id},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200, r.text

    call_args = mock_plan_store.update.call_args
    updated = call_args[0][1]  # second positional arg is the data dict

    assert "热情" in updated["persona"]["style"]
    assert "煽动" in updated["persona"]["style"]
    assert "买它" in updated["persona"]["catchphrases"]
    assert "OMG" in updated["persona"]["catchphrases"]

    titles = [s["title"] for s in updated["script"]["segments"]]
    assert "开场" in titles
    assert "行动号召" in titles

    opening_seg = next(s for s in updated["script"]["segments"] if s["title"] == "开场")
    assert "大家好欢迎来到直播间" in opening_seg["cue"]

    cta_seg = next(s for s in updated["script"]["segments"] if s["title"] == "行动号召")
    assert "现在下单立减" in cta_seg["cue"]


def test_import_to_plan_404_if_no_style():
    c = _client()
    c.app.state.video_asr_storage.get_style_profile = AsyncMock(return_value=None)
    r = c.post(
        "/api/intelligence/video-asr/videos/BV1ghost/import-to-plan",
        json={"plan_id": "plan-xyz"},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 404


def test_import_to_plan_404_if_no_plan():
    import json
    c = _client()
    from vision_intelligence.video_asr.models import StyleProfile
    sp = StyleProfile(
        video_id="BV1test",
        host_speaking_ratio=0.5,
        speaker_count={"host": 10, "guest": 0, "other": 0, "unknown": 0},
        top_phrases=[], catchphrases=[], opening_hooks=[], cta_patterns=[],
        transition_patterns=[], sentence_length={"p50": 10.0, "p90": 20.0, "unit": "chars"},
        tone_tags=[], english_ratio=0.0,
    )
    c.app.state.video_asr_storage.get_style_profile = AsyncMock(return_value=sp)

    from vision_live.plan_store import PlanStore
    mock_plan_store = AsyncMock(spec=PlanStore)
    mock_plan_store.get = AsyncMock(return_value=None)
    c.app.state.plan_store = mock_plan_store

    r = c.post(
        "/api/intelligence/video-asr/videos/BV1test/import-to-plan",
        json={"plan_id": "nonexistent"},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest python-packages/api/src/vision_api/video_asr_routes_test.py::test_import_to_plan_merges_style_into_persona -v
```

Expected: FAIL — endpoint not found (404 or AttributeError)

- [ ] **Step 3: 实现端点**

在 `python-packages/api/src/vision_api/video_asr_routes.py` 末尾追加（在 `search` 函数之后）：

```python
class ImportToPlanBody(BaseModel):
    plan_id: str


@router.post("/videos/{video_id}/import-to-plan")
async def import_to_plan(video_id: str, body: ImportToPlanBody, request: Request) -> dict:
    import uuid
    st = request.app.state.video_asr_storage
    plan_store = request.app.state.plan_store

    sp = await st.get_style_profile(video_id)
    if sp is None:
        raise HTTPException(404, "style profile not found — run analyze stage first")

    plan = await plan_store.get(body.plan_id)
    if plan is None:
        raise HTTPException(404, "plan not found")

    # merge persona
    persona = dict(plan.get("persona") or {})
    existing_style = persona.get("style", "")
    new_tags = "、".join(sp.tone_tags) if sp.tone_tags else ""
    if new_tags:
        persona["style"] = f"{existing_style}、{new_tags}".lstrip("、") if existing_style else new_tags

    existing_phrases = set(persona.get("catchphrases") or [])
    persona["catchphrases"] = list(existing_phrases | set(sp.catchphrases))

    # merge script segments (append, avoid duplicates by title)
    segments = list((plan.get("script") or {}).get("segments") or [])
    existing_titles = {s.get("title") for s in segments}

    if sp.opening_hooks and "开场" not in existing_titles:
        segments.insert(0, {
            "id": f"seg-{uuid.uuid4().hex[:8]}",
            "title": "开场",
            "goal": "吸引观众注意，建立信任感",
            "duration": 120,
            "cue": list(sp.opening_hooks),
            "must_say": False,
            "keywords": [],
        })

    if sp.cta_patterns and "行动号召" not in existing_titles:
        segments.append({
            "id": f"seg-{uuid.uuid4().hex[:8]}",
            "title": "行动号召",
            "goal": "引导观众下单、点击购物车",
            "duration": 60,
            "cue": list(sp.cta_patterns),
            "must_say": False,
            "keywords": [],
        })

    updated = {
        **plan,
        "persona": persona,
        "script": {"segments": segments},
    }
    await plan_store.update(body.plan_id, updated)
    return {"video_id": video_id, "plan_id": body.plan_id, "status": "merged"}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest python-packages/api/src/vision_api/video_asr_routes_test.py -v -k "import_to_plan"
```

Expected: 3 passed

- [ ] **Step 5: 运行全量后端测试**

```bash
uv run pytest python-packages/api/src/vision_api/ -q
```

Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add python-packages/api/src/vision_api/video_asr_routes.py \
        python-packages/api/src/vision_api/video_asr_routes_test.py
git commit -m "feat(asr): add import-to-plan endpoint to merge style profile into live plan"
```
