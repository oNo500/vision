'use client'

import { Button } from '@workspace/ui/components/button'
import { cn } from '@workspace/ui/lib/utils'
import { PencilIcon, TrashIcon } from 'lucide-react'
import { useState } from 'react'

import type { PipelineItem as PipelineItemType } from '@/features/live/hooks/use-live-stream'

import { PipelineItemEditor } from './pipeline-item-editor'

type Props = {
  item: PipelineItemType
  onRemove: (id: string) => void
  onEdit: (id: string, text: string, speech_prompt: string | null) => void
}

export function PipelineItem({ item, onRemove, onEdit }: Props) {
  const [editing, setEditing] = useState(false)

  return (
    <>
      <div
        className={cn(
          'group relative rounded-md border px-3 py-2 text-sm',
          item.stage === 'pending' && 'bg-muted/20',
          item.stage === 'synthesized' && 'border-border bg-muted/40',
        )}
      >
        {item.urgent && (
          <span
            data-testid={`urgent-badge-${item.id}`}
            className="absolute left-1 top-1 size-2 rounded-full bg-red-500"
          />
        )}
        <p className="leading-relaxed">{item.content}</p>
        {item.speech_prompt && (
          <p className="mt-0.5 text-[10px] text-muted-foreground">{item.speech_prompt}</p>
        )}
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
