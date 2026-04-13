'use client'

import { use, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'

import { Button } from '@workspace/ui/components/button'
import { Input } from '@workspace/ui/components/input'
import { Label } from '@workspace/ui/components/label'

import { combine } from '@atlaskit/pragmatic-drag-and-drop/combine'
import { draggable, dropTargetForElements, monitorForElements } from '@atlaskit/pragmatic-drag-and-drop/element/adapter'
import { attachInstruction, extractInstruction, type Instruction } from '@atlaskit/pragmatic-drag-and-drop-hitbox/list-item'
import { DropIndicator } from '@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/list-item'
import { reorder } from '@atlaskit/pragmatic-drag-and-drop/reorder'

import { appPaths } from '@/config/app-paths'
import { usePlan, type Segment } from '@/features/live/hooks/use-plan'
import { usePlans } from '@/features/live/hooks/use-plans'

function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const [input, setInput] = useState('')
  function add() {
    const trimmed = input.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setInput('')
  }
  return (
    <div className="flex flex-wrap gap-1">
      {value.map((tag) => (
        <span key={tag} className="flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-sm">
          {tag}
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => onChange(value.filter((t) => t !== tag))}
          >
            x
          </button>
        </span>
      ))}
      <input
        className="min-w-24 rounded border px-2 py-0.5 text-sm outline-none"
        value={input}
        placeholder={placeholder}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
        onBlur={add}
      />
    </div>
  )
}

function SegmentCard({
  seg,
  index,
  total,
  onUpdate,
  onRemove,
}: {
  seg: Segment
  index: number
  total: number
  onUpdate: <K extends keyof Segment>(key: K, value: Segment[K]) => void
  onRemove: () => void
}) {
  const cardRef = useRef<HTMLDivElement>(null)
  const handleRef = useRef<HTMLDivElement>(null)
  const [closestEdge, setClosestEdge] = useState<Instruction | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    const card = cardRef.current
    const handle = handleRef.current
    if (!card || !handle) return

    return combine(
      draggable({
        element: card,
        dragHandle: handle,
        getInitialData: () => ({ type: 'segment', index }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
      }),
      dropTargetForElements({
        element: card,
        canDrop: ({ source }) => source.data.type === 'segment' && source.data.index !== index,
        getData: ({ input, element }) =>
          attachInstruction({ type: 'segment', index }, {
            element,
            input,
            operations: { 'reorder-before': 'available', 'reorder-after': 'available' },
            axis: 'vertical',
          }),
        onDrag: ({ self }) => {
          setClosestEdge(extractInstruction(self.data))
        },
        onDragLeave: () => setClosestEdge(null),
        onDrop: () => setClosestEdge(null),
      }),
    )
  }, [index])

  return (
    <div
      ref={cardRef}
      className={`relative rounded border p-4 flex flex-col gap-3 ${isDragging ? 'opacity-40' : ''}`}
    >
      {closestEdge && <DropIndicator instruction={closestEdge} />}
      <div className="flex items-center gap-2">
        <div
          ref={handleRef}
          className="cursor-grab text-muted-foreground select-none px-1 text-lg"
          title="拖拽排序"
        >
          &#10815;
        </div>
        <Input
          className="flex-1"
          value={seg.title}
          onChange={(e) => onUpdate('title', e.target.value)}
          placeholder="阶段名称，如：产品介绍、限时促单"
        />
        <span className="text-xs text-muted-foreground">{index + 1}/{total}</span>
        <Button variant="ghost" size="sm" onClick={onRemove}>x</Button>
      </div>
      <textarea
        className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        value={seg.goal}
        onChange={(e) => onUpdate('goal', e.target.value)}
        rows={2}
        placeholder="告诉 AI 这段做什么，如：重点介绍益生菌成分，引导观众点购物车"
      />
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">锚点话术（AI 会在合适时机自然说出）</span>
        <TagInput
          value={seg.cue}
          onChange={(v) => onUpdate('cue', v)}
          placeholder="回车添加，AI 会在合适时机自然融入"
        />
      </div>
      <div className="flex gap-4 items-center text-sm flex-wrap">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={seg.must_say}
            onChange={(e) => onUpdate('must_say', e.target.checked)}
          />
          锚点话术必须全部说完
        </label>
        <label className="flex items-center gap-2">
          时长(秒)
          <Input
            type="number"
            className="w-20"
            value={seg.duration}
            onChange={(e) => onUpdate('duration', Number(e.target.value))}
          />
        </label>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">关键词</span>
        <TagInput value={seg.keywords} onChange={(v) => onUpdate('keywords', v)} placeholder="回车添加" />
      </div>
    </div>
  )
}

export default function PlanEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { plan, saving, savePlan } = usePlan(id)
  const { loadPlan } = usePlans()
  const [tab, setTab] = useState<'product' | 'persona' | 'script'>('product')
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return monitorForElements({
      canMonitor: ({ source }) => source.data.type === 'segment',
      onDrop({ source, location }) {
        if (!plan) return
        const target = location.current.dropTargets[0]
        if (!target) return
        const instruction = extractInstruction(target.data)
        if (!instruction) return
        const startIndex = source.data.index as number
        const targetIndex = target.data.index as number
        const finishIndex = instruction.operation === 'reorder-before' ? targetIndex : targetIndex + 1
        if (startIndex === finishIndex) return
        const reordered = reorder({
          list: plan.script.segments,
          startIndex,
          finishIndex,
        })
        savePlan({ ...plan, script: { segments: reordered } })
      },
    })
  }, [plan, savePlan])

  if (!plan) return <div className="p-6 text-sm text-muted-foreground">加载中…</div>

  function updateProduct(key: string, value: unknown) {
    if (!plan) return
    savePlan({ ...plan, product: { ...plan.product, [key]: value } })
  }

  function updatePersona(key: string, value: unknown) {
    if (!plan) return
    savePlan({ ...plan, persona: { ...plan.persona, [key]: value } })
  }

  function updateSegment<K extends keyof Segment>(index: number, key: K, value: Segment[K]) {
    if (!plan) return
    const segments = plan.script.segments.map((s, i) =>
      i === index ? { ...s, [key]: value } : s
    )
    savePlan({ ...plan, script: { segments } })
  }

  function addSegment() {
    if (!plan) return
    const newSeg: Segment = {
      id: `seg-${Date.now()}`,
      title: '',
      goal: '',
      duration: 300,
      cue: [],
      must_say: false,
      keywords: [],
    }
    savePlan({ ...plan, script: { segments: [...plan.script.segments, newSeg] } })
  }

  function removeSegment(index: number) {
    if (!plan) return
    const segments = plan.script.segments.filter((_, i) => i !== index)
    savePlan({ ...plan, script: { segments } })
  }

  async function handleSaveAndLoad() {
    await savePlan(plan)
    const ok = await loadPlan(id)
    if (ok) router.push(appPaths.dashboard.live.href)
  }

  const tabs = [
    { key: 'product', label: '产品信息' },
    { key: 'persona', label: '人设风格' },
    { key: 'script', label: '直播脚本' },
  ] as const

  return (
    <div className="flex h-full flex-col">
      {/* header */}
      <div className="flex items-center gap-4 border-b px-6 py-3">
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => router.push(appPaths.dashboard.livePlans.href)}
        >
          &larr; 方案库
        </button>
        <Input
          className="max-w-xs text-sm font-semibold"
          value={plan.name}
          onChange={(e) => savePlan({ ...plan, name: e.target.value })}
        />
      </div>

      {/* body */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* tabs */}
        <div className="flex w-32 shrink-0 flex-col gap-1 border-r p-3">
          {tabs.map(({ key, label }) => (
            <button
              type="button"
              key={key}
              className={`rounded px-3 py-2 text-left text-sm ${tab === key ? 'bg-muted font-medium' : 'text-muted-foreground hover:text-foreground'}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {/* content */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === 'product' && (
            <div className="flex flex-col gap-4 max-w-lg">
              <div className="flex flex-col gap-1.5">
                <Label>产品名称</Label>
                <Input value={plan.product.name} onChange={(e) => updateProduct('name', e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>描述</Label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  value={plan.product.description}
                  onChange={(e) => updateProduct('description', e.target.value)}
                  rows={3}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>价格</Label>
                <Input value={plan.product.price} onChange={(e) => updateProduct('price', e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>亮点</Label>
                <TagInput value={plan.product.highlights} onChange={(v) => updateProduct('highlights', v)} placeholder="回车添加" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>FAQ</Label>
                {plan.product.faq.map((item, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <Input placeholder="问题" value={item.question} onChange={(e) => {
                      const faq = plan.product.faq.map((f, j) => j === i ? { ...f, question: e.target.value } : f)
                      updateProduct('faq', faq)
                    }} />
                    <Input placeholder="回答" value={item.answer} onChange={(e) => {
                      const faq = plan.product.faq.map((f, j) => j === i ? { ...f, answer: e.target.value } : f)
                      updateProduct('faq', faq)
                    }} />
                    <Button variant="ghost" size="sm" onClick={() => updateProduct('faq', plan.product.faq.filter((_, j) => j !== i))}>x</Button>
                  </div>
                ))}
                <Button variant="outline" size="sm" className="self-start" onClick={() => updateProduct('faq', [...plan.product.faq, { question: '', answer: '' }])}>+ 添加 FAQ</Button>
              </div>
            </div>
          )}

          {tab === 'persona' && (
            <div className="flex flex-col gap-4 max-w-lg">
              <div className="flex flex-col gap-1.5">
                <Label>主播名称</Label>
                <Input value={plan.persona.name} onChange={(e) => updatePersona('name', e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>风格</Label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  value={plan.persona.style}
                  onChange={(e) => updatePersona('style', e.target.value)}
                  rows={2}
                  placeholder="如：温柔亲切，专业可信"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>口头禅</Label>
                <TagInput value={plan.persona.catchphrases} onChange={(v) => updatePersona('catchphrases', v)} placeholder="回车添加" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>禁用词</Label>
                <TagInput value={plan.persona.forbidden_words} onChange={(v) => updatePersona('forbidden_words', v)} placeholder="回车添加" />
              </div>
            </div>
          )}

          {tab === 'script' && (
            <div className="flex flex-col gap-3" ref={listRef}>
              {plan.script.segments.map((seg, i) => (
                <SegmentCard
                  key={seg.id}
                  seg={seg}
                  index={i}
                  total={plan.script.segments.length}
                  onUpdate={(key, value) => updateSegment(i, key, value)}
                  onRemove={() => removeSegment(i)}
                />
              ))}
              <Button variant="outline" className="self-start" onClick={addSegment}>+ 添加段落</Button>
            </div>
          )}
        </div>
      </div>

      {/* bottom bar */}
      <div className="flex gap-2 border-t px-6 py-3">
        <Button variant="outline" onClick={() => savePlan(plan)} disabled={saving}>保存</Button>
        <Button onClick={handleSaveAndLoad} disabled={saving}>保存并加载</Button>
      </div>
    </div>
  )
}
