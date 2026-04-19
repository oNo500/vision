# Video ASR Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Next.js 前端中添加 Video ASR 功能模块，包括视频列表、提交任务、实时进度、查看转录/摘要。

**Architecture:** Feature-based 架构，新增 `features/video-asr/` 模块，包含 hooks（数据层）和 components（UI 层）。新增路由 `app/(dashboard)/video-asr/` 和 `app/(dashboard)/video-asr/[videoId]/`。API 通过 `apiFetch` 和 `EventSource` 与后端 `/api/intelligence/video-asr/` 通信。

**Tech Stack:** Next.js 16 App Router、React 19、@workspace/ui (shadcn)、Tailwind CSS v4、@infra-x/fwrap、EventSource SSE

---

## File Structure

```
apps/web/src/
├── config/
│   └── app-paths.ts                          (modify) add video-asr paths
├── components/
│   └── app-sidebar.tsx                       (modify) add Video ASR nav item
├── app/(dashboard)/
│   ├── video-asr/
│   │   ├── page.tsx                          (create) video list + submit job
│   │   └── [videoId]/
│   │       └── page.tsx                      (create) video detail + progress + transcript
└── features/video-asr/
    ├── hooks/
    │   ├── use-videos.ts                     (create) list all videos (polling)
    │   ├── use-submit-job.ts                 (create) POST /jobs mutation
    │   ├── use-video-progress.ts             (create) SSE progress stream
    │   └── use-video-detail.ts              (create) video metadata + transcript/summary
    └── components/
        ├── video-list/
        │   ├── index.tsx                     (create) video list page component
        │   └── video-list.test.tsx
        ├── submit-job-dialog/
        │   ├── index.tsx                     (create) URL input dialog
        │   └── submit-job-dialog.test.tsx
        ├── video-progress/
        │   ├── index.tsx                     (create) SSE progress panel
        │   └── video-progress.test.tsx
        └── video-detail/
            ├── index.tsx                     (create) transcript + summary viewer
            └── video-detail.test.tsx
```

---

### Task 1: API 类型 + app-paths + 导航

**Files:**
- Modify: `apps/web/src/config/app-paths.ts`
- Modify: `apps/web/src/components/app-sidebar.tsx`

- [ ] **Step 1: 在 app-paths.ts 中添加 video-asr 路由**

```typescript
// apps/web/src/config/app-paths.ts
export const appPaths = {
  home: { href: '/' },
  dashboard: {
    live: { href: '/live' },
    plans: { href: '/plans' },
    plan: (id: string) => ({ href: `/plans/${id}` }),
    planRag: (id: string) => ({ href: `/plans/${id}/rag` }),
    libraries: { href: '/libraries' },
    library: (id: string) => ({ href: `/libraries/${id}` }),
    videoAsr: { href: '/video-asr' },
    videoAsrDetail: (videoId: string) => ({ href: `/video-asr/${videoId}` }),
  },
}
```

- [ ] **Step 2: 在 app-sidebar.tsx 中添加导航项**

在现有 `navItems` 数组中添加（在 Libraries 之后）：

```typescript
import { FileVideoIcon } from 'lucide-react'
// ...
{
  title: '视频转录',
  url: appPaths.dashboard.videoAsr.href,
  icon: <FileVideoIcon />,
  items: [],
},
```

- [ ] **Step 3: 提交**

```bash
git add apps/web/src/config/app-paths.ts apps/web/src/components/app-sidebar.tsx
git commit -m "feat(video-asr): add routes and nav item"
```

---

### Task 2: use-videos hook（视频列表）

**Files:**
- Create: `apps/web/src/features/video-asr/hooks/use-videos.ts`

后端接口：`GET /api/intelligence/video-asr/videos`

返回类型（来自后端 `list_videos` + `get_video_source`）：
```json
[
  {
    "video_id": "BV1xxx",
    "url": "https://...",
    "source": "bilibili",
    "title": "视频标题",
    "uploader": "UP主",
    "duration_sec": 1234,
    "asr_model": "gemini-2.5-flash",
    "processed_at": "2026-04-19T..."
  }
]
```

- [ ] **Step 1: 写测试**

创建 `apps/web/src/features/video-asr/hooks/use-videos.test.ts`：

```typescript
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useVideos } from './use-videos'

vi.mock('@/lib/api-fetch', () => ({
  apiFetch: vi.fn(),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

describe('useVideos', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('returns videos on success', async () => {
    const { apiFetch } = await import('@/lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({
      ok: true,
      status: 200,
      data: [{ video_id: 'BV1abc', title: 'Test', url: 'https://example.com', source: 'bilibili', uploader: 'UP', duration_sec: 100, asr_model: 'gemini', processed_at: '' }],
    })
    const { result } = renderHook(() => useVideos())
    await waitFor(() => expect(result.current.videos).toHaveLength(1))
    expect(result.current.videos[0].video_id).toBe('BV1abc')
  })

  it('returns empty array on error', async () => {
    const { apiFetch } = await import('@/lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({ ok: false, status: 500 })
    const { result } = renderHook(() => useVideos())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.videos).toEqual([])
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiu/code/vision
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-videos.test.ts
```

Expected: FAIL with "Cannot find module"

- [ ] **Step 3: 实现 hook**

创建 `apps/web/src/features/video-asr/hooks/use-videos.ts`：

```typescript
'use client'

import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api-fetch'

export type VideoItem = {
  video_id: string
  url: string
  source: string
  title: string | null
  uploader: string | null
  duration_sec: number | null
  asr_model: string
  processed_at: string
}

export function useVideos() {
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const res = await apiFetch<VideoItem[]>('api/intelligence/video-asr/videos', { silent: true })
    if (res.ok) setVideos(res.data)
    setLoading(false)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { videos, loading, refresh }
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-videos.test.ts
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/hooks/
git commit -m "feat(video-asr): add use-videos hook"
```

---

### Task 3: use-submit-job hook（提交任务）

**Files:**
- Create: `apps/web/src/features/video-asr/hooks/use-submit-job.ts`

后端接口：`POST /api/intelligence/video-asr/jobs`，body `{ urls: string[] }`，需要 API Key header `X-API-Key`（从 `env.NEXT_PUBLIC_API_KEY` 读取，若有）。

实际上后端的 API Key middleware 只保护 `/api/intelligence/` 前缀，所以前端需要在请求头带上 key。查看 `env.ts` 确认是否已有 `NEXT_PUBLIC_API_KEY`。

> **注意**：如果 env.ts 中没有 `NEXT_PUBLIC_API_KEY`，需要在此 task 中添加（可选字段，默认空字符串）。

- [ ] **Step 1: 检查 env.ts 是否有 API Key 配置**

```bash
grep -n "API_KEY\|api_key" /Users/xiu/code/vision/apps/web/src/config/env.ts
```

- [ ] **Step 2: 若无，在 env.ts 中添加**

```typescript
// 在 client 块中添加：
NEXT_PUBLIC_API_KEY: z.string().optional().default(''),
// 在 runtimeEnv 块中添加：
NEXT_PUBLIC_API_KEY: process.env.NEXT_PUBLIC_API_KEY,
```

- [ ] **Step 3: 写测试**

创建 `apps/web/src/features/video-asr/hooks/use-submit-job.test.ts`：

```typescript
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useSubmitJob } from './use-submit-job'

vi.mock('@/lib/api-fetch', () => ({
  apiFetch: vi.fn(),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: 'test-key' },
}))

describe('useSubmitJob', () => {
  it('submits URLs and returns job_id on success', async () => {
    const { apiFetch } = await import('@/lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({
      ok: true, status: 200,
      data: { job_id: 'job-123', video_ids: ['BV1abc'], status: 'accepted' },
    })
    const { result } = renderHook(() => useSubmitJob())
    let jobId: string | null = null
    await act(async () => {
      jobId = await result.current.submit(['https://www.bilibili.com/video/BV1abc'])
    })
    expect(jobId).toBe('job-123')
    expect(result.current.submitting).toBe(false)
  })

  it('returns null on failure', async () => {
    const { apiFetch } = await import('@/lib/api-fetch')
    vi.mocked(apiFetch).mockResolvedValue({ ok: false, status: 400 })
    const { result } = renderHook(() => useSubmitJob())
    let jobId: string | null = 'sentinel'
    await act(async () => {
      jobId = await result.current.submit(['https://invalid'])
    })
    expect(jobId).toBeNull()
  })
})
```

- [ ] **Step 4: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-submit-job.test.ts
```

- [ ] **Step 5: 实现 hook**

创建 `apps/web/src/features/video-asr/hooks/use-submit-job.ts`：

```typescript
'use client'

import { useCallback, useState } from 'react'
import { env } from '@/config/env'
import { apiFetch } from '@/lib/api-fetch'

type JobResponse = {
  job_id: string
  video_ids: string[]
  status: string
}

export function useSubmitJob() {
  const [submitting, setSubmitting] = useState(false)

  const submit = useCallback(async (urls: string[]): Promise<string | null> => {
    setSubmitting(true)
    const res = await apiFetch<JobResponse>('api/intelligence/video-asr/jobs', {
      method: 'POST',
      body: { urls },
      headers: env.NEXT_PUBLIC_API_KEY ? { 'X-API-Key': env.NEXT_PUBLIC_API_KEY } : {},
      fallbackError: '提交任务失败',
    })
    setSubmitting(false)
    return res.ok ? res.data.job_id : null
  }, [])

  return { submit, submitting }
}
```

- [ ] **Step 6: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-submit-job.test.ts
```

- [ ] **Step 7: 提交**

```bash
git add apps/web/src/features/video-asr/hooks/use-submit-job.ts apps/web/src/config/env.ts
git commit -m "feat(video-asr): add use-submit-job hook"
```

---

### Task 4: use-video-progress hook（SSE 实时进度）

**Files:**
- Create: `apps/web/src/features/video-asr/hooks/use-video-progress.ts`

后端 SSE 接口：`GET /api/intelligence/video-asr/videos/{videoId}/progress`

推送事件格式（每 2 秒或有变化时）：
```json
{
  "stages": [
    { "stage": "ingest", "status": "done", "duration_sec": 12.3 },
    { "stage": "transcribe", "status": "running", "duration_sec": null }
  ],
  "transcribe_progress": {
    "done": 4,
    "total": 12,
    "chunks": [{"id": 0, "engine": "gemini-2.5-flash"}, {"id": 1, "engine": "funasr-paraformer-large"}]
  },
  "cost_usd": 0.0123
}
```

- [ ] **Step 1: 写测试**

创建 `apps/web/src/features/video-asr/hooks/use-video-progress.test.ts`：

```typescript
import { renderHook, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))

// Mock EventSource
class MockEventSource {
  static instance: MockEventSource | null = null
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  onopen: (() => void) | null = null
  close = vi.fn()
  constructor(public url: string) {
    MockEventSource.instance = this
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }
}
vi.stubGlobal('EventSource', MockEventSource)

import { useVideoProgress } from './use-video-progress'

describe('useVideoProgress', () => {
  afterEach(() => {
    MockEventSource.instance = null
    vi.clearAllMocks()
  })

  it('parses progress events', () => {
    const { result } = renderHook(() => useVideoProgress('BV1abc'))
    act(() => {
      MockEventSource.instance?.emit({
        stages: [{ stage: 'ingest', status: 'done', duration_sec: 5 }],
        transcribe_progress: { done: 2, total: 4, chunks: [] },
        cost_usd: 0.01,
      })
    })
    expect(result.current.stages).toHaveLength(1)
    expect(result.current.stages[0].status).toBe('done')
    expect(result.current.transcribeProgress.done).toBe(2)
    expect(result.current.costUsd).toBe(0.01)
  })

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useVideoProgress('BV1abc'))
    unmount()
    expect(MockEventSource.instance?.close).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-video-progress.test.ts
```

- [ ] **Step 3: 实现 hook**

创建 `apps/web/src/features/video-asr/hooks/use-video-progress.ts`：

```typescript
'use client'

import { useEffect, useState } from 'react'
import { env } from '@/config/env'

export type StageStatus = {
  stage: string
  status: 'running' | 'done' | 'failed' | 'pending'
  duration_sec: number | null
}

export type ChunkInfo = {
  id: number
  engine: string
}

export type TranscribeProgress = {
  done: number
  total: number | null
  chunks: ChunkInfo[]
}

export type VideoProgressState = {
  stages: StageStatus[]
  transcribeProgress: TranscribeProgress
  costUsd: number
  finished: boolean
  connected: boolean
}

const INITIAL: VideoProgressState = {
  stages: [],
  transcribeProgress: { done: 0, total: null, chunks: [] },
  costUsd: 0,
  finished: false,
  connected: false,
}

const STAGE_ORDER = ['ingest', 'preprocess', 'transcribe', 'merge', 'render', 'analyze', 'load']

export function useVideoProgress(videoId: string): VideoProgressState {
  const [state, setState] = useState<VideoProgressState>(INITIAL)

  useEffect(() => {
    const url = `${env.NEXT_PUBLIC_API_URL}/api/intelligence/video-asr/videos/${videoId}/progress`
    const es = new EventSource(url)

    es.onopen = () => setState((s) => ({ ...s, connected: true }))
    es.onerror = () => setState((s) => ({ ...s, connected: false }))

    es.addEventListener('progress', (e: Event) => {
      const msg = e as MessageEvent
      try {
        const data = JSON.parse(msg.data as string) as {
          stages: StageStatus[]
          transcribe_progress: TranscribeProgress
          cost_usd: number
        }
        const statuses = new Map(data.stages.map((s) => [s.stage, s.status]))
        const finished =
          data.stages.length === STAGE_ORDER.length &&
          STAGE_ORDER.every((s) => statuses.get(s) === 'done' || statuses.get(s) === 'failed')
        setState({
          stages: data.stages,
          transcribeProgress: data.transcribe_progress,
          costUsd: data.cost_usd,
          finished,
          connected: true,
        })
      } catch {
        // ignore malformed frames
      }
    })

    return () => es.close()
  }, [videoId])

  return state
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-video-progress.test.ts
```

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/hooks/use-video-progress.ts apps/web/src/features/video-asr/hooks/use-video-progress.test.ts
git commit -m "feat(video-asr): add use-video-progress SSE hook"
```

---

### Task 5: use-video-detail hook（视频详情）

**Files:**
- Create: `apps/web/src/features/video-asr/hooks/use-video-detail.ts`

后端接口：
- `GET /api/intelligence/video-asr/videos/{videoId}` → 视频元数据
- `GET /api/intelligence/video-asr/videos/{videoId}/transcript.md` → 转录 Markdown（PlainText）
- `GET /api/intelligence/video-asr/videos/{videoId}/summary` → 摘要 Markdown（PlainText）

- [ ] **Step 1: 写测试**

创建 `apps/web/src/features/video-asr/hooks/use-video-detail.test.ts`：

```typescript
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useVideoDetail } from './use-video-detail'

vi.mock('@/lib/api-fetch', () => ({
  apiFetch: vi.fn(),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

describe('useVideoDetail', () => {
  it('fetches metadata, transcript and summary in parallel', async () => {
    const { apiFetch } = await import('@/lib/api-fetch')
    vi.mocked(apiFetch)
      .mockResolvedValueOnce({ ok: true, status: 200, data: { video_id: 'BV1abc', title: 'Test', url: 'https://x.com', source: 'bilibili', uploader: 'U', duration_sec: 60, asr_model: 'gemini', processed_at: '' } })
      .mockResolvedValueOnce({ ok: true, status: 200, data: '## Transcript\nHello' })
      .mockResolvedValueOnce({ ok: true, status: 200, data: '## Summary\nWorld' })

    const { result } = renderHook(() => useVideoDetail('BV1abc'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.meta?.title).toBe('Test')
    expect(result.current.transcriptMd).toBe('## Transcript\nHello')
    expect(result.current.summaryMd).toBe('## Summary\nWorld')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-video-detail.test.ts
```

- [ ] **Step 3: 实现 hook**

创建 `apps/web/src/features/video-asr/hooks/use-video-detail.ts`：

```typescript
'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api-fetch'
import type { VideoItem } from './use-videos'

type VideoDetail = {
  meta: VideoItem | null
  transcriptMd: string | null
  summaryMd: string | null
  loading: boolean
}

export function useVideoDetail(videoId: string): VideoDetail {
  const [meta, setMeta] = useState<VideoItem | null>(null)
  const [transcriptMd, setTranscriptMd] = useState<string | null>(null)
  const [summaryMd, setSummaryMd] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const base = `api/intelligence/video-asr/videos/${videoId}`
    Promise.all([
      apiFetch<VideoItem>(base, { silent: true }),
      apiFetch<string>(`${base}/transcript.md`, { silent: true }),
      apiFetch<string>(`${base}/summary`, { silent: true }),
    ]).then(([metaRes, transcriptRes, summaryRes]) => {
      if (metaRes.ok) setMeta(metaRes.data)
      if (transcriptRes.ok) setTranscriptMd(transcriptRes.data)
      if (summaryRes.ok) setSummaryMd(summaryRes.data)
      setLoading(false)
    })
  }, [videoId])

  return { meta, transcriptMd, summaryMd, loading }
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/hooks/use-video-detail.test.ts
```

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/hooks/
git commit -m "feat(video-asr): add use-video-detail hook"
```

---

### Task 6: SubmitJobDialog 组件

**Files:**
- Create: `apps/web/src/features/video-asr/components/submit-job-dialog/index.tsx`
- Create: `apps/web/src/features/video-asr/components/submit-job-dialog/submit-job-dialog.test.tsx`

使用 shadcn `Dialog`、`Button`、`Input`（来自 `@workspace/ui`）。

- [ ] **Step 1: 写测试**

```typescript
// apps/web/src/features/video-asr/components/submit-job-dialog/submit-job-dialog.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SubmitJobDialog } from './index'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))
vi.mock('@/lib/api-fetch', () => ({ apiFetch: vi.fn() }))

describe('SubmitJobDialog', () => {
  it('calls onSubmit with parsed URLs', async () => {
    const onSubmit = vi.fn().mockResolvedValue('job-1')
    render(<SubmitJobDialog open onOpenChange={() => {}} onSubmit={onSubmit} submitting={false} />)
    const textarea = screen.getByPlaceholderText(/URL/)
    fireEvent.change(textarea, { target: { value: 'https://www.bilibili.com/video/BV1abc\nhttps://www.bilibili.com/video/BV2def' } })
    fireEvent.click(screen.getByRole('button', { name: /提交/ }))
    expect(onSubmit).toHaveBeenCalledWith(['https://www.bilibili.com/video/BV1abc', 'https://www.bilibili.com/video/BV2def'])
  })

  it('disables submit when input is empty', () => {
    render(<SubmitJobDialog open onOpenChange={() => {}} onSubmit={vi.fn()} submitting={false} />)
    expect(screen.getByRole('button', { name: /提交/ })).toBeDisabled()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/submit-job-dialog/submit-job-dialog.test.tsx
```

- [ ] **Step 3: 实现组件**

```typescript
// apps/web/src/features/video-asr/components/submit-job-dialog/index.tsx
'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@workspace/ui/components/dialog'
import { Textarea } from '@workspace/ui/components/textarea'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (urls: string[]) => Promise<string | null>
  submitting: boolean
}

export function SubmitJobDialog({ open, onOpenChange, onSubmit, submitting }: Props) {
  const [input, setInput] = useState('')

  const urls = input
    .split('\n')
    .map((u) => u.trim())
    .filter(Boolean)

  async function handleSubmit() {
    const jobId = await onSubmit(urls)
    if (jobId) {
      setInput('')
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>提交视频转录任务</DialogTitle>
        </DialogHeader>
        <Textarea
          placeholder="每行一个 URL，支持 B 站、YouTube"
          rows={6}
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={urls.length === 0 || submitting} onClick={handleSubmit}>
            {submitting ? '提交中...' : '提交'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/submit-job-dialog/submit-job-dialog.test.tsx
```

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/components/submit-job-dialog/
git commit -m "feat(video-asr): add SubmitJobDialog component"
```

---

### Task 7: VideoList 组件

**Files:**
- Create: `apps/web/src/features/video-asr/components/video-list/index.tsx`
- Create: `apps/web/src/features/video-asr/components/video-list/video-list.test.tsx`

显示视频列表，每行：标题（或 video_id）、来源、时长、处理时间，点击跳转详情页。

- [ ] **Step 1: 写测试**

```typescript
// apps/web/src/features/video-asr/components/video-list/video-list.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { VideoList } from './index'
import type { VideoItem } from '@/features/video-asr/hooks/use-videos'

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

const mockVideos: VideoItem[] = [
  { video_id: 'BV1abc', url: 'https://x.com', source: 'bilibili', title: '测试视频', uploader: 'UP主', duration_sec: 3661, asr_model: 'gemini', processed_at: '2026-04-19T00:00:00' },
]

describe('VideoList', () => {
  it('renders video title', () => {
    render(<VideoList videos={mockVideos} loading={false} />)
    expect(screen.getByText('测试视频')).toBeDefined()
  })

  it('shows loading state', () => {
    render(<VideoList videos={[]} loading={true} />)
    expect(screen.getByText(/加载中/)).toBeDefined()
  })

  it('shows empty state when no videos', () => {
    render(<VideoList videos={[]} loading={false} />)
    expect(screen.getByText(/暂无视频/)).toBeDefined()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/video-list/video-list.test.tsx
```

- [ ] **Step 3: 实现组件**

```typescript
// apps/web/src/features/video-asr/components/video-list/index.tsx
'use client'

import Link from 'next/link'
import { appPaths } from '@/config/app-paths'
import type { VideoItem } from '@/features/video-asr/hooks/use-videos'

function formatDuration(sec: number | null): string {
  if (sec === null) return '--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`
}

type Props = {
  videos: VideoItem[]
  loading: boolean
}

export function VideoList({ videos, loading }: Props) {
  if (loading) {
    return <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">加载中...</div>
  }
  if (videos.length === 0) {
    return <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">暂无视频，点击右上角提交任务</div>
  }
  return (
    <div className="divide-y">
      {videos.map((v) => (
        <Link
          key={v.video_id}
          href={appPaths.dashboard.videoAsrDetail(v.video_id).href}
          className="flex items-center gap-4 px-4 py-3 text-sm hover:bg-muted/50 transition-colors"
        >
          <div className="flex-1 min-w-0">
            <div className="font-medium truncate">{v.title ?? v.video_id}</div>
            <div className="text-xs text-muted-foreground truncate">{v.uploader ?? ''} · {v.source}</div>
          </div>
          <div className="shrink-0 text-xs text-muted-foreground tabular-nums">{formatDuration(v.duration_sec)}</div>
          <div className="shrink-0 text-xs text-muted-foreground">{v.processed_at ? new Date(v.processed_at).toLocaleDateString('zh-CN') : ''}</div>
        </Link>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/video-list/video-list.test.tsx
```

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/components/video-list/
git commit -m "feat(video-asr): add VideoList component"
```

---

### Task 8: VideoProgress 组件

**Files:**
- Create: `apps/web/src/features/video-asr/components/video-progress/index.tsx`
- Create: `apps/web/src/features/video-asr/components/video-progress/video-progress.test.tsx`

显示 7 个阶段状态（图标 + 名称 + 耗时），转录阶段显示 chunk 进度条，底部显示费用。

- [ ] **Step 1: 写测试**

```typescript
// apps/web/src/features/video-asr/components/video-progress/video-progress.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { VideoProgress } from './index'
import type { VideoProgressState } from '@/features/video-asr/hooks/use-video-progress'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))

const mockState: VideoProgressState = {
  stages: [
    { stage: 'ingest', status: 'done', duration_sec: 5.2 },
    { stage: 'preprocess', status: 'done', duration_sec: 30.1 },
    { stage: 'transcribe', status: 'running', duration_sec: null },
  ],
  transcribeProgress: { done: 4, total: 12, chunks: [{ id: 0, engine: 'gemini-2.5-flash' }, { id: 1, engine: 'funasr-paraformer-large' }] },
  costUsd: 0.0456,
  finished: false,
  connected: true,
}

describe('VideoProgress', () => {
  it('renders all provided stage statuses', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText('ingest')).toBeDefined()
    expect(screen.getByText('transcribe')).toBeDefined()
  })

  it('shows chunk progress for transcribe stage', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText('4 / 12')).toBeDefined()
  })

  it('shows cost', () => {
    render(<VideoProgress state={mockState} />)
    expect(screen.getByText(/0\.0456/)).toBeDefined()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/video-progress/video-progress.test.tsx
```

- [ ] **Step 3: 实现组件**

```typescript
// apps/web/src/features/video-asr/components/video-progress/index.tsx
'use client'

import type { VideoProgressState } from '@/features/video-asr/hooks/use-video-progress'

const STAGE_LABELS: Record<string, string> = {
  ingest: '下载',
  preprocess: '预处理',
  transcribe: '转录',
  merge: '合并',
  render: '渲染',
  analyze: '分析',
  load: '入库',
}

const STATUS_ICON: Record<string, string> = {
  done: '●',
  running: '◎',
  failed: '✗',
  pending: '○',
}

const STATUS_COLOR: Record<string, string> = {
  done: 'text-green-500',
  running: 'text-blue-500 animate-pulse',
  failed: 'text-red-500',
  pending: 'text-muted-foreground',
}

type Props = {
  state: VideoProgressState
}

export function VideoProgress({ state }: Props) {
  const stageMap = new Map(state.stages.map((s) => [s.stage, s]))
  const allStages = ['ingest', 'preprocess', 'transcribe', 'merge', 'render', 'analyze', 'load']
  const { done, total, chunks } = state.transcribeProgress

  return (
    <div className="space-y-3 font-mono text-sm">
      {allStages.map((name) => {
        const s = stageMap.get(name)
        const status = s?.status ?? 'pending'
        return (
          <div key={name} className="flex items-center gap-3">
            <span className={`w-4 text-center ${STATUS_COLOR[status]}`}>{STATUS_ICON[status]}</span>
            <span className="w-20 text-muted-foreground">{STAGE_LABELS[name] ?? name}</span>
            <span className="w-16 text-xs text-muted-foreground tabular-nums">
              {s?.duration_sec != null ? `${s.duration_sec.toFixed(1)}s` : ''}
            </span>
            {name === 'transcribe' && status === 'running' && (
              <span className="text-xs text-muted-foreground">{done} / {total ?? '?'}</span>
            )}
          </div>
        )
      })}

      {chunks.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {chunks.map((c) => (
            <span
              key={c.id}
              title={c.engine}
              className={`px-1.5 py-0.5 rounded text-xs ${c.engine.startsWith('funasr') ? 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300' : 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'}`}
            >
              {c.engine.startsWith('funasr') ? 'F' : 'G'}
            </span>
          ))}
        </div>
      )}

      {state.costUsd > 0 && (
        <div className="pt-2 text-xs text-muted-foreground">
          费用: ${state.costUsd.toFixed(4)}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/video-progress/video-progress.test.tsx
```

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/components/video-progress/
git commit -m "feat(video-asr): add VideoProgress component"
```

---

### Task 9: VideoDetail 组件

**Files:**
- Create: `apps/web/src/features/video-asr/components/video-detail/index.tsx`
- Create: `apps/web/src/features/video-asr/components/video-detail/video-detail.test.tsx`

显示视频元数据 + 进度面板 + Tab（转录 / 摘要）。

- [ ] **Step 1: 写测试**

```typescript
// apps/web/src/features/video-asr/components/video-detail/video-detail.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { VideoDetail } from './index'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))
vi.mock('@/features/video-asr/hooks/use-video-progress', () => ({
  useVideoProgress: () => ({
    stages: [],
    transcribeProgress: { done: 0, total: null, chunks: [] },
    costUsd: 0,
    finished: true,
    connected: false,
  }),
}))
vi.mock('@/features/video-asr/hooks/use-video-detail', () => ({
  useVideoDetail: () => ({
    meta: { video_id: 'BV1abc', title: '测试视频', uploader: 'UP主', source: 'bilibili', duration_sec: 120, url: 'https://x.com', asr_model: 'gemini', processed_at: '' },
    transcriptMd: '## 转录内容',
    summaryMd: '## 摘要内容',
    loading: false,
  }),
}))

describe('VideoDetail', () => {
  it('renders video title', () => {
    render(<VideoDetail videoId="BV1abc" />)
    expect(screen.getByText('测试视频')).toBeDefined()
  })

  it('renders transcript tab content', () => {
    render(<VideoDetail videoId="BV1abc" />)
    expect(screen.getByText('## 转录内容')).toBeDefined()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/video-detail/video-detail.test.tsx
```

- [ ] **Step 3: 实现组件**

```typescript
// apps/web/src/features/video-asr/components/video-detail/index.tsx
'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { useVideoDetail } from '@/features/video-asr/hooks/use-video-detail'
import { useVideoProgress } from '@/features/video-asr/hooks/use-video-progress'
import { VideoProgress } from '@/features/video-asr/components/video-progress'

type Tab = 'transcript' | 'summary'

type Props = {
  videoId: string
}

export function VideoDetail({ videoId }: Props) {
  const { meta, transcriptMd, summaryMd, loading } = useVideoDetail(videoId)
  const progressState = useVideoProgress(videoId)
  const [tab, setTab] = useState<Tab>('transcript')

  if (loading) {
    return <div className="p-8 text-sm text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
      {/* Meta */}
      {meta && (
        <div className="text-sm">
          <h2 className="text-base font-semibold">{meta.title ?? videoId}</h2>
          <div className="mt-1 text-xs text-muted-foreground">
            {meta.uploader} · {meta.source} · {meta.duration_sec != null ? `${Math.round(meta.duration_sec / 60)} 分钟` : ''}
          </div>
        </div>
      )}

      {/* Progress */}
      {!progressState.finished && (
        <div className="rounded-md border p-3">
          <VideoProgress state={progressState} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2">
        <Button size="sm" variant={tab === 'transcript' ? 'default' : 'outline'} onClick={() => setTab('transcript')}>转录</Button>
        <Button size="sm" variant={tab === 'summary' ? 'default' : 'outline'} onClick={() => setTab('summary')}>摘要</Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto rounded-md border p-4">
        {tab === 'transcript' && (
          transcriptMd
            ? <pre className="whitespace-pre-wrap text-sm">{transcriptMd}</pre>
            : <div className="text-sm text-muted-foreground">转录尚未完成</div>
        )}
        {tab === 'summary' && (
          summaryMd
            ? <pre className="whitespace-pre-wrap text-sm">{summaryMd}</pre>
            : <div className="text-sm text-muted-foreground">摘要尚未完成</div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm --filter @vision/web test run apps/web/src/features/video-asr/components/video-detail/video-detail.test.tsx
```

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/features/video-asr/components/video-detail/
git commit -m "feat(video-asr): add VideoDetail component"
```

---

### Task 10: 路由页面

**Files:**
- Create: `apps/web/src/app/(dashboard)/video-asr/page.tsx`
- Create: `apps/web/src/app/(dashboard)/video-asr/[videoId]/page.tsx`

- [ ] **Step 1: 创建视频列表页**

```typescript
// apps/web/src/app/(dashboard)/video-asr/page.tsx
'use client'

import { useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import { PageHeader } from '@/components/page-header'
import { SubmitJobDialog } from '@/features/video-asr/components/submit-job-dialog'
import { VideoList } from '@/features/video-asr/components/video-list'
import { useSubmitJob } from '@/features/video-asr/hooks/use-submit-job'
import { useVideos } from '@/features/video-asr/hooks/use-videos'

export default function VideoAsrPage() {
  const { videos, loading, refresh } = useVideos()
  const { submit, submitting } = useSubmitJob()
  const [dialogOpen, setDialogOpen] = useState(false)

  async function handleSubmit(urls: string[]) {
    const jobId = await submit(urls)
    if (jobId) refresh()
    return jobId
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <PageHeader>
        <h1 className="text-sm font-semibold">视频转录</h1>
        <div className="flex-1" />
        <Button size="sm" onClick={() => setDialogOpen(true)}>提交任务</Button>
      </PageHeader>

      <div className="flex-1 overflow-auto">
        <VideoList videos={videos} loading={loading} />
      </div>

      <SubmitJobDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmit}
        submitting={submitting}
      />
    </div>
  )
}
```

- [ ] **Step 2: 创建视频详情页**

```typescript
// apps/web/src/app/(dashboard)/video-asr/[videoId]/page.tsx
'use client'

import { use } from 'react'
import Link from 'next/link'
import { ChevronLeftIcon } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { VideoDetail } from '@/features/video-asr/components/video-detail'
import { appPaths } from '@/config/app-paths'

export default function VideoAsrDetailPage({ params }: { params: Promise<{ videoId: string }> }) {
  const { videoId } = use(params)
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <PageHeader>
        <Link href={appPaths.dashboard.videoAsr.href} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronLeftIcon className="size-4" />
          视频转录
        </Link>
        <span className="text-sm font-mono text-muted-foreground">{videoId}</span>
      </PageHeader>
      <VideoDetail videoId={videoId} />
    </div>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add apps/web/src/app/(dashboard)/video-asr/
git commit -m "feat(video-asr): add page routes"
```

---

### Task 11: 类型检查 + 全量测试

- [ ] **Step 1: 运行类型检查**

```bash
cd /Users/xiu/code/vision/apps/web
pnpm tsc --noEmit
```

修复所有类型错误。

- [ ] **Step 2: 运行全量测试**

```bash
cd /Users/xiu/code/vision
pnpm --filter @vision/web test run
```

确保所有测试通过。

- [ ] **Step 3: 提交**

```bash
git add -p
git commit -m "fix(video-asr): type and test fixes"
```
