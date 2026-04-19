# ASR → Plan Frontend Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在方案编辑页的人设/脚本 Tab 加"从视频导入"按钮，在方案 RAG 页加视频导入入口，复用后端两个新端点。

**Architecture:** 三个入口全部在方案编辑侧新增，不改动视频详情页。人设/脚本 Tab 各加一个触发 Sheet 的按钮，选视频后调 `import-to-plan`；方案 RAG 页（`/plans/[id]/rag`）在 `PlanRagLibraries` 组件下方新增"从视频导入到素材库"区域，复用现有 `ImportTranscriptTab` 组件，调 `rag-libraries/{lib_id}/import-transcript`。

**Tech Stack:** React 19, Next.js 16, TypeScript, Vitest, @testing-library/react

---

## File Map

| 文件 | 变更 |
|------|------|
| `apps/web/src/features/live/hooks/use-plan.ts` | 添加 `importStyleFromVideo(videoId, planId)` 方法 |
| `apps/web/src/features/live/components/import-style-sheet/index.tsx` | 新建：视频选择 Sheet，触发 import-to-plan |
| `apps/web/src/app/(dashboard)/plans/[id]/page.tsx` | persona/script tab 各加"从视频导入"按钮 |
| `apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx` | 加"从视频导入到素材库"区块，需要先选库 |
| `apps/web/src/features/live/components/import-style-sheet/import-style-sheet.test.tsx` | 新建测试 |

---

### Task 1: use-plan hook 添加 importStyleFromVideo

**Files:**
- Modify: `apps/web/src/features/live/hooks/use-plan.ts`

- [ ] **Step 1: 写失败测试**

在 `apps/web/src/features/live/hooks/` 新建 `use-plan.test.ts`：

```typescript
import { renderHook, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({ apiFetch: (...args: unknown[]) => mockApiFetch(...args) }))

vi.mock('@workspace/ui/components/sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { usePlan } from './use-plan'

const ok = (data: unknown) => ({ ok: true, data, status: 200 })
const fail = (status = 500) => ({ ok: false, data: null, status })

describe('usePlan.importStyleFromVideo', () => {
  afterEach(() => vi.clearAllMocks())

  it('calls import-to-plan endpoint and returns true on success', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok({ id: 'plan-1', name: 'Test', product: {}, persona: {}, script: { segments: [] } }))
      .mockResolvedValueOnce(ok({ video_id: 'BV1abc', plan_id: 'plan-1', status: 'merged' }))

    const { result } = renderHook(() => usePlan('plan-1'))
    let success: boolean | undefined
    await act(async () => {
      success = await result.current.importStyleFromVideo('BV1abc')
    })
    expect(success).toBe(true)
    expect(mockApiFetch).toHaveBeenCalledWith(
      'api/intelligence/video-asr/videos/BV1abc/import-to-plan',
      expect.objectContaining({ method: 'POST', body: { plan_id: 'plan-1' } }),
    )
  })

  it('returns false on API error', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok({ id: 'plan-1', name: 'Test', product: {}, persona: {}, script: { segments: [] } }))
      .mockResolvedValueOnce(fail(404))

    const { result } = renderHook(() => usePlan('plan-1'))
    let success: boolean | undefined
    await act(async () => {
      success = await result.current.importStyleFromVideo('BV1abc')
    })
    expect(success).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiu/code/vision/apps/web
pnpm vitest run src/features/live/hooks/use-plan.test.ts
```

Expected: FAIL — `importStyleFromVideo` is not a function

- [ ] **Step 3: 在 use-plan.ts 添加 importStyleFromVideo**

在 `apps/web/src/features/live/hooks/use-plan.ts` 的 `savePlan` 定义之后，`return` 之前添加：

```typescript
  const importStyleFromVideo = useCallback(
    async (videoId: string): Promise<boolean> => {
      const res = await apiFetch<{ video_id: string; plan_id: string; status: string }>(
        `api/intelligence/video-asr/videos/${videoId}/import-to-plan`,
        { method: 'POST', body: { plan_id: id }, fallbackError: '导入失败' },
      )
      if (res.ok) {
        toast.success('风格已导入，重新加载方案中…')
        await fetchPlan()
      }
      return res.ok
    },
    [id, fetchPlan],
  )
```

并在 `return` 语句中加入 `importStyleFromVideo`：

```typescript
  return { plan, saving, savePlan, fetchPlan, importStyleFromVideo }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm vitest run src/features/live/hooks/use-plan.test.ts
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/live/hooks/use-plan.ts \
        apps/web/src/features/live/hooks/use-plan.test.ts
git commit -m "feat(plan): add importStyleFromVideo to usePlan hook"
```

---

### Task 2: ImportStyleSheet 组件

新建视频选择 Sheet。打开后展示已完成转录的视频列表，用户选择一个后调 `importStyleFromVideo`。

**Files:**
- Create: `apps/web/src/features/live/components/import-style-sheet/index.tsx`
- Create: `apps/web/src/features/live/components/import-style-sheet/import-style-sheet.test.tsx`

- [ ] **Step 1: 写失败测试**

新建 `apps/web/src/features/live/components/import-style-sheet/import-style-sheet.test.tsx`：

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))
vi.mock('@workspace/ui/components/sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({ apiFetch: (...args: unknown[]) => mockApiFetch(...args) }))

import { ImportStyleSheet } from './index'

const videos = [
  { video_id: 'BV1abc', title: '测试视频', source: 'bilibili', duration_sec: 240 },
]

describe('ImportStyleSheet', () => {
  afterEach(() => vi.clearAllMocks())

  it('shows video list when open', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
    render(
      <ImportStyleSheet open onOpenChange={vi.fn()} onImport={vi.fn()} />
    )
    await waitFor(() => expect(screen.getByText('测试视频')).toBeDefined())
  })

  it('calls onImport with video_id when button clicked', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
    const onImport = vi.fn().mockResolvedValue(true)
    render(
      <ImportStyleSheet open onOpenChange={vi.fn()} onImport={onImport} />
    )
    await waitFor(() => screen.getByText('测试视频'))
    fireEvent.click(screen.getByRole('button', { name: '导入' }))
    await waitFor(() => expect(onImport).toHaveBeenCalledWith('BV1abc'))
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm vitest run src/features/live/components/import-style-sheet/import-style-sheet.test.tsx
```

Expected: FAIL — cannot find module `./index`

- [ ] **Step 3: 实现组件**

新建 `apps/web/src/features/live/components/import-style-sheet/index.tsx`：

```tsx
'use client'

import { useEffect, useState } from 'react'
import { Button } from '@workspace/ui/components/button'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@workspace/ui/components/sheet'
import { apiFetch } from '@/lib/api-fetch'

type VideoSummary = {
  video_id: string
  title: string | null
  source: string
  duration_sec: number | null
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImport: (videoId: string) => Promise<boolean>
}

export function ImportStyleSheet({ open, onOpenChange, onImport }: Props) {
  const [videos, setVideos] = useState<VideoSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [imported, setImported] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!open) return
    apiFetch<VideoSummary[]>('api/intelligence/video-asr/videos', { silent: true }).then(
      (res) => { if (res.ok) setVideos(res.data) },
    )
  }, [open])

  async function handleImport(videoId: string) {
    setLoading(true)
    try {
      const ok = await onImport(videoId)
      if (ok) {
        setImported((prev) => new Set([...prev, videoId]))
        onOpenChange(false)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>从视频导入风格</SheetTitle>
        </SheetHeader>
        <p className="mt-2 text-sm text-muted-foreground">
          选择一个已转录的视频，将其口头禅、开场话术、行动号召模式导入当前方案的人设与脚本。
        </p>
        {videos.length === 0 ? (
          <div className="mt-6 text-sm text-muted-foreground">暂无已完成的转录视频。</div>
        ) : (
          <div className="mt-4 flex flex-col divide-y">
            {videos.map((v) => {
              const durationMin = v.duration_sec ? Math.round(v.duration_sec / 60) : null
              const isImported = imported.has(v.video_id)
              return (
                <div key={v.video_id} className="flex items-center justify-between gap-3 py-3">
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-sm">{v.title ?? v.video_id}</span>
                    <span className="text-xs text-muted-foreground">
                      {v.source}{durationMin ? ` · ${durationMin}分钟` : ''}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant={isImported ? 'outline' : 'default'}
                    disabled={loading}
                    onClick={() => handleImport(v.video_id)}
                  >
                    {isImported ? '已导入' : '导入'}
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm vitest run src/features/live/components/import-style-sheet/import-style-sheet.test.tsx
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/live/components/import-style-sheet/
git commit -m "feat(plan): add ImportStyleSheet component for video style import"
```

---

### Task 3: 方案编辑页 persona/script tab 加入口

在 `plans/[id]/page.tsx` 的 persona tab 和 script tab 各加一个"从视频导入"按钮，点击打开 `ImportStyleSheet`。

**Files:**
- Modify: `apps/web/src/app/(dashboard)/plans/[id]/page.tsx`

- [ ] **Step 1: 在 persona tab 添加按钮**

在 `apps/web/src/app/(dashboard)/plans/[id]/page.tsx` 顶部 import 区添加：

```tsx
import { ImportStyleSheet } from '@/features/live/components/import-style-sheet'
```

在 `PlanEditorPage` 函数体内，`const [tab, setTab]` 下方添加状态：

```tsx
const [importSheetOpen, setImportSheetOpen] = useState(false)
```

在 `const { plan, saving, savePlan } = usePlan(id)` 改为：

```tsx
const { plan, saving, savePlan, importStyleFromVideo } = usePlan(id)
```

找到 persona tab 内容区：

```tsx
{tab === 'persona' && (
  <div className="flex flex-col gap-4 max-w-lg">
    <div className="flex flex-col gap-1.5">
      <Label>主播名称</Label>
```

改为：

```tsx
{tab === 'persona' && (
  <div className="flex flex-col gap-4 max-w-lg">
    <div className="flex justify-end">
      <Button variant="outline" size="sm" onClick={() => setImportSheetOpen(true)}>
        从视频导入风格
      </Button>
    </div>
    <div className="flex flex-col gap-1.5">
      <Label>主播名称</Label>
```

找到 script tab 内容区：

```tsx
{tab === 'script' && (
  <div className="flex flex-col gap-3" ref={listRef}>
    {plan.script.segments.map((seg, i) => (
```

改为：

```tsx
{tab === 'script' && (
  <div className="flex flex-col gap-3" ref={listRef}>
    <div className="flex justify-end">
      <Button variant="outline" size="sm" onClick={() => setImportSheetOpen(true)}>
        从视频导入话术段落
      </Button>
    </div>
    {plan.script.segments.map((seg, i) => (
```

在组件 return 的最外层 `<div>` 的 closing tag 前（`</div>` 之前），添加：

```tsx
    <ImportStyleSheet
      open={importSheetOpen}
      onOpenChange={setImportSheetOpen}
      onImport={importStyleFromVideo}
    />
```

- [ ] **Step 2: 类型检查**

```bash
cd /Users/xiu/code/vision/apps/web && pnpm typecheck
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/\(dashboard\)/plans/\[id\]/page.tsx
git commit -m "feat(plan): add import style buttons to persona and script tabs"
```

---

### Task 4: 方案 RAG 页加视频导入到素材库

在 `/plans/[id]/rag/page.tsx` 页面，`PlanRagLibraries` 下方加一个"从视频导入到素材库"区块。用户先选择目标素材库，再选择视频，调现有 `useRagLibrary(libId).importTranscript(videoId)`。

**Files:**
- Modify: `apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx`
- Create: `apps/web/src/features/live/components/rag-library/import-to-library-panel.tsx`

- [ ] **Step 1: 写失败测试（ImportToLibraryPanel）**

新建 `apps/web/src/features/live/components/rag-library/import-to-library-panel.test.tsx`：

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))
vi.mock('@workspace/ui/components/sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({ apiFetch: (...args: unknown[]) => mockApiFetch(...args) }))

import { ImportToLibraryPanel } from './import-to-library-panel'

const libraries = [
  { id: 'lib-a', name: '素材库A', created_at: '' },
]
const videos = [
  { video_id: 'BV1abc', title: '测试视频', source: 'bilibili', duration_sec: 240 },
]

describe('ImportToLibraryPanel', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders library selector', () => {
    render(<ImportToLibraryPanel libraries={libraries} />)
    expect(screen.getByText('素材库A')).toBeDefined()
  })

  it('shows video list after library selected', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
    render(<ImportToLibraryPanel libraries={libraries} />)
    fireEvent.click(screen.getByText('素材库A'))
    await waitFor(() => expect(screen.getByText('测试视频')).toBeDefined())
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pnpm vitest run src/features/live/components/rag-library/import-to-library-panel.test.tsx
```

Expected: FAIL — cannot find module

- [ ] **Step 3: 实现 ImportToLibraryPanel 组件**

新建 `apps/web/src/features/live/components/rag-library/import-to-library-panel.tsx`：

```tsx
'use client'

import { useState } from 'react'
import type { RagLibrary } from '@/features/live/hooks/use-rag-libraries'
import { useRagLibrary } from '@/features/live/hooks/use-rag-library'
import { ImportTranscriptTab } from './import-transcript-tab'

type Props = {
  libraries: RagLibrary[]
}

export function ImportToLibraryPanel({ libraries }: Props) {
  const [selectedLibId, setSelectedLibId] = useState<string | null>(null)

  if (libraries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        暂无素材库，请先在「素材库」页面创建。
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {libraries.map((lib) => (
          <button
            key={lib.id}
            type="button"
            onClick={() => setSelectedLibId(lib.id)}
            className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
              selectedLibId === lib.id
                ? 'border-foreground bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {lib.name}
          </button>
        ))}
      </div>

      {selectedLibId && (
        <LibraryImporter libId={selectedLibId} />
      )}
    </div>
  )
}

function LibraryImporter({ libId }: { libId: string }) {
  const { importTranscript } = useRagLibrary(libId)
  return <ImportTranscriptTab onImport={importTranscript} />
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pnpm vitest run src/features/live/components/rag-library/import-to-library-panel.test.tsx
```

Expected: 2 passed

- [ ] **Step 5: 在 RAG 页面添加 ImportToLibraryPanel**

改造 `apps/web/src/app/(dashboard)/plans/[id]/rag/page.tsx`：

```tsx
'use client'

import { use } from 'react'
import { useRouter } from 'next/navigation'

import { appPaths } from '@/config/app-paths'
import { PlanRagLibraries } from '@/features/live/components/plan-rag-libraries'
import { ImportToLibraryPanel } from '@/features/live/components/rag-library/import-to-library-panel'
import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'

export default function PlanRagPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { libraries } = useRagLibraries()

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b px-6 py-3">
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => router.push(appPaths.dashboard.plan(id).href)}
        >
          ← 方案编辑
        </button>
      </div>
      <div className="flex-1 overflow-y-auto divide-y">
        <PlanRagLibraries planId={id} />
        <div className="p-6 flex flex-col gap-3">
          <h2 className="text-base font-semibold">从视频导入到素材库</h2>
          <p className="text-sm text-muted-foreground">
            选择目标素材库，再选择视频，将主播话术片段导入供检索使用。
          </p>
          <ImportToLibraryPanel libraries={libraries} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: 类型检查**

```bash
cd /Users/xiu/code/vision/apps/web && pnpm typecheck
```

Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/app/\(dashboard\)/plans/\[id\]/rag/page.tsx \
        apps/web/src/features/live/components/rag-library/import-to-library-panel.tsx \
        apps/web/src/features/live/components/rag-library/import-to-library-panel.test.tsx
git commit -m "feat(plan): add video import to library panel on plan rag page"
```

---

### Task 5: 全量前端测试验证

- [ ] **Step 1: 运行全量前端测试**

```bash
cd /Users/xiu/code/vision/apps/web
pnpm vitest run
```

Expected: all passed

- [ ] **Step 2: 类型检查**

```bash
pnpm typecheck
```

Expected: no errors
