'use client'

import { monitorForElements } from '@atlaskit/pragmatic-drag-and-drop/element/adapter'
import { extractInstruction } from '@atlaskit/pragmatic-drag-and-drop-hitbox/list-item'
import { reorder } from '@atlaskit/pragmatic-drag-and-drop/reorder'
import { useEffect } from 'react'

import type { PipelineItem as PipelineItemType } from '@/features/live/hooks/use-live-stream'

import { PipelineItem } from './pipeline-item'

type Stage = 'pending' | 'synthesized'

type Props = {
  title: string
  stage: Stage
  items: PipelineItemType[]
  onRemove: (id: string) => void
  onEdit: (id: string, text: string, speech_prompt: string | null) => void
  onReorder: (stage: Stage, newIds: string[]) => void
}

export function StageSection({ title, stage, items, onRemove, onEdit, onReorder }: Props) {
  useEffect(() => {
    return monitorForElements({
      canMonitor: ({ source }) =>
        source.data.type === 'pipeline-item' && source.data.stage === stage,
      onDrop({ source, location }) {
        const target = location.current.dropTargets[0]
        if (!target) return
        const instruction = extractInstruction(target.data)
        if (!instruction) return
        if (source.data.stage !== stage) return
        const startIndex = source.data.index as number
        const targetIndex = target.data.index as number
        const finishIndex = instruction.operation === 'reorder-before' ? targetIndex : targetIndex + 1
        if (startIndex === finishIndex) return
        const reordered = reorder({ list: items, startIndex, finishIndex })
        onReorder(stage, reordered.map((it) => it.id))
      },
    })
  }, [items, onReorder, stage])

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
          {items.map((item, idx) => (
            <PipelineItem
              key={item.id}
              item={item}
              index={idx}
              stage={stage}
              onRemove={onRemove}
              onEdit={onEdit}
            />
          ))}
        </div>
      )}
    </section>
  )
}
