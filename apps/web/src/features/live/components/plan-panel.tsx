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
      <SheetContent side="right" className="w-[480px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{plan.name}</SheetTitle>
        </SheetHeader>

        <div className="mt-4 space-y-6 text-sm">
          {/* product */}
          <section>
            <h3 className="mb-2 font-semibold">产品</h3>
            <p className="font-medium">{plan.product.name}</p>
            {plan.product.price && <p className="text-muted-foreground">价格：{plan.product.price}</p>}
            {plan.product.description && <p className="mt-1 text-muted-foreground">{plan.product.description}</p>}
            {plan.product.highlights.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-muted-foreground">
                {plan.product.highlights.map((h, i) => <li key={i}>· {h}</li>)}
              </ul>
            )}
            {plan.product.faq.length > 0 && (
              <div className="mt-3 space-y-2">
                <p className="font-medium text-foreground">常见问题</p>
                {plan.product.faq.map((f, i) => (
                  <div key={i}>
                    <p className="font-medium">Q: {f.question}</p>
                    <p className="text-muted-foreground">A: {f.answer}</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* persona */}
          <section>
            <h3 className="mb-2 font-semibold">人设</h3>
            <p><span className="text-muted-foreground">名称：</span>{plan.persona.name}</p>
            {plan.persona.style && <p><span className="text-muted-foreground">风格：</span>{plan.persona.style}</p>}
            {plan.persona.catchphrases.length > 0 && (
              <div className="mt-2">
                <p className="text-muted-foreground">口头禅</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {plan.persona.catchphrases.map((c, i) => (
                    <span key={i} className="rounded bg-muted px-2 py-0.5 text-xs">{c}</span>
                  ))}
                </div>
              </div>
            )}
            {plan.persona.forbidden_words.length > 0 && (
              <div className="mt-2">
                <p className="text-muted-foreground">禁用词</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {plan.persona.forbidden_words.map((w, i) => (
                    <span key={i} className="rounded bg-destructive/10 px-2 py-0.5 text-xs text-destructive">{w}</span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* script */}
          <section>
            <h3 className="mb-2 font-semibold">脚本（{plan.script.segments.length} 段）</h3>
            <div className="space-y-3">
              {plan.script.segments.map((seg, i) => (
                <div key={seg.id} className="rounded border p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{i + 1}</span>
                    <span className="font-medium">{seg.title || seg.id}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {Math.floor(seg.duration / 60)}min
                    </span>
                  </div>
                  {seg.goal && <p className="text-xs text-muted-foreground">{seg.goal}</p>}
                  {seg.cue.length > 0 && (
                    <div className="mt-2 rounded border-l-2 border-primary/40 pl-2">
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        话术{seg.must_say ? '（必说）' : '（融入）'}
                      </p>
                      {seg.cue.map((line, j) => (
                        <p key={j} className="text-xs">· {line}</p>
                      ))}
                    </div>
                  )}
                  {seg.keywords.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {seg.keywords.map((kw, j) => (
                        <span key={j} className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{kw}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
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
    <div className="border-b px-5 py-2 text-sm">
      <div className="flex items-center gap-3">
        <span className="font-medium">{plan.name}</span>
        <span className="text-xs text-muted-foreground">
          {plan.product.name}{plan.product.price ? ` · ${plan.product.price}` : ''} · {plan.script.segments.length} 段
        </span>
        <PlanPreviewSheet plan={plan} />
        <Link
          href={appPaths.dashboard.livePlans.href}
          className="ml-auto text-xs text-muted-foreground underline"
        >
          切换方案 ↗
        </Link>
      </div>
    </div>
  )
}
