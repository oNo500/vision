'use client'

import { useCallback, useEffect, useState } from 'react'

import Link from 'next/link'

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@workspace/ui/components/sheet'

import { appPaths } from '@/config/app-paths'
import { env } from '@/config/env'
import type { LivePlan } from '@/features/live/hooks/use-plan'

function PlanPreviewSheet({ plan }: { plan: LivePlan }) {
  return (
    <Sheet>
      <SheetTrigger className="rounded px-2 py-0.5 text-xs hover:bg-muted">
        预览方案
      </SheetTrigger>
      <SheetContent side="right" className="flex w-[520px] flex-col gap-0 overflow-hidden p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle className="text-base">{plan.name}</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4 text-sm">
          {/* product */}
          <div className="mb-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">产品</p>
            <p className="font-medium">{plan.product.name}</p>
            {plan.product.price && (
              <p className="mt-0.5 text-muted-foreground">{plan.product.price}</p>
            )}
            {plan.product.description && (
              <p className="mt-2 leading-relaxed text-muted-foreground">{plan.product.description}</p>
            )}
            {plan.product.highlights.length > 0 && (
              <ul className="mt-3 space-y-1">
                {plan.product.highlights.map((h, i) => (
                  <li key={i} className="flex gap-2 text-muted-foreground">
                    <span className="mt-0.5 shrink-0 text-primary">✓</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            )}
            {plan.product.faq.length > 0 && (
              <div className="mt-4 space-y-3 rounded-lg bg-muted/50 p-3">
                <p className="text-xs font-medium text-muted-foreground">常见问题</p>
                {plan.product.faq.map((f, i) => (
                  <div key={i} className="space-y-0.5">
                    <p className="font-medium">Q：{f.question}</p>
                    <p className="text-muted-foreground">A：{f.answer}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mb-6 border-t pt-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">人设</p>
            <div className="flex gap-4">
              <div>
                <p className="text-xs text-muted-foreground">名称</p>
                <p className="mt-0.5 font-medium">{plan.persona.name}</p>
              </div>
              {plan.persona.style && (
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">风格</p>
                  <p className="mt-0.5">{plan.persona.style}</p>
                </div>
              )}
            </div>
            {plan.persona.catchphrases.length > 0 && (
              <div className="mt-3">
                <p className="mb-1.5 text-xs text-muted-foreground">口头禅</p>
                <div className="flex flex-wrap gap-1.5">
                  {plan.persona.catchphrases.map((c, i) => (
                    <span key={i} className="rounded-full border px-2.5 py-0.5 text-xs">{c}</span>
                  ))}
                </div>
              </div>
            )}
            {plan.persona.forbidden_words.length > 0 && (
              <div className="mt-3">
                <p className="mb-1.5 text-xs text-muted-foreground">禁用词</p>
                <div className="flex flex-wrap gap-1.5">
                  {plan.persona.forbidden_words.map((w, i) => (
                    <span key={i} className="rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs text-destructive">{w}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* script */}
          <div className="border-t pt-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              脚本 · {plan.script.segments.length} 段 · 共 {Math.round(plan.script.segments.reduce((s, g) => s + g.duration, 0) / 60)} 分钟
            </p>
            <div className="space-y-2">
              {plan.script.segments.map((seg, i) => (
                <div key={seg.id} className="rounded-lg border bg-background">
                  <div className="flex items-center gap-2.5 px-3 py-2.5">
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-mono font-semibold text-muted-foreground">
                      {i + 1}
                    </span>
                    <span className="flex-1 font-medium">{seg.title || seg.id}</span>
                    <span className="text-xs text-muted-foreground">
                      {seg.duration >= 60 ? `${Math.floor(seg.duration / 60)}min` : `${seg.duration}s`}
                    </span>
                  </div>
                  {(seg.goal || seg.cue.length > 0 || seg.keywords.length > 0) && (
                    <div className="space-y-2 border-t px-3 pb-3 pt-2">
                      {seg.goal && (
                        <p className="text-xs leading-relaxed text-muted-foreground">{seg.goal}</p>
                      )}
                      {seg.cue.length > 0 && (
                        <div className="rounded border-l-2 border-primary/50 bg-primary/5 py-1.5 pl-3 pr-2">
                          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-primary/70">
                            话术 {seg.must_say ? '· 必说' : '· 融入'}
                          </p>
                          <ul className="space-y-0.5">
                            {seg.cue.map((line, j) => (
                              <li key={j} className="text-xs text-foreground">{line}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {seg.keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {seg.keywords.map((kw, j) => (
                            <span key={j} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{kw}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function PlanPanel() {
  const [plan, setPlan] = useState<LivePlan | null>(null)

  const fetchActive = useCallback(async () => {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans/active`)
      if (res.ok) {
        const data = await res.json()
        setPlan(data.plan ?? null)
      }
    } catch { /* backend unreachable */ }
  }, [])

  useEffect(() => { fetchActive() }, [fetchActive])

  if (!plan) {
    return (
      <div className="border-b px-5 py-2 text-sm text-muted-foreground">
        未加载方案 —{' '}
        <Link href={appPaths.dashboard.livePlans.href} className="underline">
          前往方案库
        </Link>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3 border-b px-5 py-2 text-sm">
      <span className="font-medium">{plan.name}</span>
      <span className="text-xs text-muted-foreground">
        {plan.product.name}{plan.product.price ? ` · ${plan.product.price}` : ''} · {plan.script.segments.length} 段
      </span>
      <PlanPreviewSheet plan={plan} />
      <Link href={appPaths.dashboard.livePlans.href} className="ml-auto text-xs text-muted-foreground underline">
        切换方案 ↗
      </Link>
    </div>
  )
}
