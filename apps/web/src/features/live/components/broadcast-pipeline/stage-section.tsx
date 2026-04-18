'use client'

import { monitorForElements } from '@atlaskit/pragmatic-drag-and-drop/element/adapter'
import { extractInstruction } from '@atlaskit/pragmatic-drag-and-drop-hitbox/list-item'
import { reorder } from '@atlaskit/pragmatic-drag-and-drop/reorder'
import { useEffect, useRef } from 'react'

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
  /** Fixed pixel height for the scrollable list region. Keeps layout stable as items come and go. */
  listHeight: number
}

export function StageSection({ title, stage, items, onRemove, onEdit, onReorder, listHeight }: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const userScrolledRef = useRef(false)

  // Auto-stick to bottom (the "next to leave" end) when idle.
  // Once the user scrolls up, respect that until they scroll back to bottom.
  useEffect(() => {
    const el = listRef.current
    if (!el) return
    if (!userScrolledRef.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [items])

  function handleScroll() {
    const el = listRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 4
    userScrolledRef.current = !atBottom
  }

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
    <section className="flex shrink-0 flex-col gap-1.5 p-3">
      <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <span>{title}</span>
        <span>{items.length}</span>
      </div>
      <div
        ref={listRef}
        onScroll={handleScroll}
        className="flex flex-col gap-1.5 overflow-y-auto"
        style={{ height: listHeight }}
      >
        {items.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">—</p>
        ) : (
          items.map((_, displayIdx) => {
            const dataIdx = items.length - 1 - displayIdx
            const item = items[dataIdx]
            if (!item) return null
            return (
              <PipelineItem
                key={item.id}
                item={item}
                index={dataIdx}
                stage={stage}
                onRemove={onRemove}
                onEdit={onEdit}
              />
            )
          })
        )}
      </div>
    </section>
  )
}
