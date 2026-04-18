'use client'

import { ChevronDownIcon, ChevronUpIcon } from 'lucide-react'
import { useState } from 'react'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

export function HistorySection({ items }: { items: PipelineItem[] }) {
  const [open, setOpen] = useState(false)

  return (
    <section className="border-t">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
        onClick={() => setOpen((o) => !o)}
      >
        <span>已播完（{items.length}）</span>
        {open ? <ChevronUpIcon className="size-3" /> : <ChevronDownIcon className="size-3" />}
      </button>
      {open && (
        <div className="flex flex-col gap-1 px-3 pb-3">
          {items.slice(-100).toReversed().map((item) => (
            <div
              key={item.id}
              className="rounded border border-dashed px-2 py-1 text-xs text-muted-foreground"
            >
              {item.content}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
