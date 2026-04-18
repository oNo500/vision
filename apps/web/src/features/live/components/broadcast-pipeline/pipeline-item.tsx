'use client'

import { combine } from '@atlaskit/pragmatic-drag-and-drop/combine'
import {
  draggable,
  dropTargetForElements,
} from '@atlaskit/pragmatic-drag-and-drop/element/adapter'
import {
  attachInstruction,
  extractInstruction,
  type Instruction,
} from '@atlaskit/pragmatic-drag-and-drop-hitbox/list-item'
import { DropIndicator } from '@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/list-item'
import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { GripVerticalIcon, PencilIcon, TrashIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { PipelineItem as PipelineItemType } from '@/features/live/hooks/use-live-stream'

import { PipelineItemEditor } from './pipeline-item-editor'

type Props = {
  item: PipelineItemType
  index: number
  stage: 'pending' | 'synthesized'
  onRemove: (id: string) => void
  onEdit: (id: string, text: string, speech_prompt: string | null) => void
}

export function PipelineItem({ item, index, stage, onRemove, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [closestEdge, setClosestEdge] = useState<Instruction | null>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const handleRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const card = cardRef.current
    const handle = handleRef.current
    if (!card || !handle) return

    return combine(
      draggable({
        element: card,
        dragHandle: handle,
        getInitialData: () => ({ type: 'pipeline-item', stage, index, id: item.id }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
      }),
      dropTargetForElements({
        element: card,
        canDrop: ({ source }) =>
          source.data.type === 'pipeline-item' &&
          source.data.stage === stage &&
          source.data.id !== item.id,
        getData: ({ input, element }) =>
          attachInstruction(
            { type: 'pipeline-item', stage, index, id: item.id },
            {
              element,
              input,
              operations: { 'reorder-before': 'available', 'reorder-after': 'available' },
              axis: 'vertical',
            },
          ),
        onDrag: ({ self }) => setClosestEdge(extractInstruction(self.data)),
        onDragLeave: () => setClosestEdge(null),
        onDrop: () => setClosestEdge(null),
      }),
    )
  }, [item.id, index, stage])

  return (
    <>
      <div
        ref={cardRef}
        className={cn(
          'group relative rounded-md border px-3 py-2 text-sm',
          item.stage === 'pending' && 'bg-muted/20',
          item.stage === 'synthesized' && 'border-border bg-muted/40',
          isDragging && 'opacity-40',
        )}
      >
        {closestEdge && <DropIndicator instruction={closestEdge} />}
        {item.urgent && (
          <span
            data-testid={`urgent-badge-${item.id}`}
            className="absolute left-1 top-1 size-2 rounded-full bg-red-500"
          />
        )}
        <div className="flex items-start gap-2">
          <div
            ref={handleRef}
            className="mt-0.5 cursor-grab text-muted-foreground select-none"
            aria-label="拖拽排序"
            title="拖拽排序"
          >
            <GripVerticalIcon className="size-3.5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="leading-relaxed">{item.content}</p>
            {item.speech_prompt && (
              <p className="mt-0.5 text-[10px] text-muted-foreground">{item.speech_prompt}</p>
            )}
          </div>
        </div>
        <div className="pointer-events-none absolute right-2 top-1/2 flex -translate-y-1/2 gap-1 opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100">
          <Button
            size="icon" variant="ghost" className="size-6"
            aria-label="编辑"
            onClick={() => setEditing(true)}
          >
            <PencilIcon className="size-3" />
          </Button>
          <Button
            size="icon" variant="ghost" className="size-6 text-destructive"
            aria-label="删除"
            onClick={() => onRemove(item.id)}
          >
            <TrashIcon className="size-3" />
          </Button>
        </div>
      </div>
      {editing && (
        <PipelineItemEditor
          item={item}
          onSave={(text, prompt) => { onEdit(item.id, text, prompt); setEditing(false) }}
          onCancel={() => setEditing(false)}
        />
      )}
    </>
  )
}
