'use client'

import type { PipelineItem as PipelineItemType } from '@/features/live/hooks/use-live-stream'

import { PipelineItem } from './pipeline-item'

type Props = {
  title: string
  items: PipelineItemType[]
  onRemove: (id: string) => void
  onEdit: (id: string, text: string, speech_prompt: string | null) => void
}

export function StageSection({ title, items, onRemove, onEdit }: Props) {
  return (
    <section className="flex flex-col gap-1.5 p-3">
      <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <span>{title}</span>
        <span>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">—</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {items.map((item) => (
            <PipelineItem key={item.id} item={item} onRemove={onRemove} onEdit={onEdit} />
          ))}
        </div>
      )}
    </section>
  )
}
