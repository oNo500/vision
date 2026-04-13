'use client'

import { use, useState } from 'react'
import { useRouter } from 'next/navigation'

import { Button } from '@workspace/ui/components/button'
import { Input } from '@workspace/ui/components/input'
import { Label } from '@workspace/ui/components/label'

import { appPaths } from '@/config/app-paths'
import { usePlan, type LivePlan, type Segment } from '@/features/live/hooks/use-plan'
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

export default function PlanEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { plan, saving, savePlan } = usePlan(id)
  const { loadPlan } = usePlans()
  const [tab, setTab] = useState<'product' | 'persona' | 'script'>('product')

  if (!plan) return <div className="p-6 text-sm text-muted-foreground">加载中…</div>

  function updateProduct(key: string, value: unknown) {
    if (!plan) return
    savePlan({ ...plan, product: { ...plan.product, [key]: value } })
  }

  function updatePersona(key: string, value: unknown) {
    if (!plan) return
    savePlan({ ...plan, persona: { ...plan.persona, [key]: value } })
  }

  function updateSegment(index: number, key: string, value: unknown) {
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
      text: '',
      duration: 60,
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

  function moveSegment(index: number, direction: 'up' | 'down') {
    if (!plan) return
    const segments = [...plan.script.segments]
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= segments.length) return
    ;[segments[index], segments[target]] = [segments[target], segments[index]]
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
            <div className="flex flex-col gap-3 max-w-2xl">
              {plan.script.segments.map((seg, i) => (
                <div key={seg.id} className="rounded border p-4 flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-6">{i + 1}</span>
                    <div className="flex gap-1 ml-auto">
                      <Button variant="ghost" size="sm" onClick={() => moveSegment(i, 'up')} disabled={i === 0}>up</Button>
                      <Button variant="ghost" size="sm" onClick={() => moveSegment(i, 'down')} disabled={i === plan.script.segments.length - 1}>down</Button>
                      <Button variant="ghost" size="sm" onClick={() => removeSegment(i)}>x</Button>
                    </div>
                  </div>
                  <textarea
                    className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    value={seg.text}
                    onChange={(e) => updateSegment(i, 'text', e.target.value)}
                    rows={2}
                    placeholder="脚本内容"
                  />
                  <div className="flex gap-4 items-center text-sm">
                    <label className="flex items-center gap-2">
                      时长(秒)
                      <Input
                        type="number"
                        className="w-20"
                        value={seg.duration}
                        onChange={(e) => updateSegment(i, 'duration', Number(e.target.value))}
                      />
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={seg.must_say}
                        onChange={(e) => updateSegment(i, 'must_say', e.target.checked)}
                      />
                      必须贴近原文
                    </label>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">关键词</span>
                    <TagInput value={seg.keywords} onChange={(v) => updateSegment(i, 'keywords', v)} placeholder="回车添加" />
                  </div>
                </div>
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
