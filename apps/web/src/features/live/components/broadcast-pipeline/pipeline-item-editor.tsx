'use client'

import { Button } from '@workspace/ui/components/button'
import { Label } from '@workspace/ui/components/label'
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@workspace/ui/components/sheet'
import { useState } from 'react'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'

type Props = {
  item: PipelineItem
  onSave: (text: string, speech_prompt: string | null) => void
  onCancel: () => void
}

export function PipelineItemEditor({ item, onSave, onCancel }: Props) {
  const [text, setText] = useState(item.content)
  const [prompt, setPrompt] = useState(item.speech_prompt ?? '')

  return (
    <Sheet open onOpenChange={(open) => !open && onCancel()}>
      <SheetContent side="right" className="flex flex-col gap-4">
        <SheetHeader>
          <SheetTitle>编辑话术</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-4">
          <div className="flex flex-col gap-1">
            <Label>文本（{text.length} 字）</Label>
            <textarea
              rows={6}
              className="resize-none rounded-md border bg-background p-2 text-sm"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>语音提示（可选）</Label>
            <textarea
              rows={3}
              className="resize-none rounded-md border bg-background p-2 text-sm"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>
          {item.stage === 'synthesized' && (
            <p className="rounded-md bg-amber-500/10 p-2 text-xs text-amber-600">
              注意：此条已合成音频。保存后将重新合成并加入待合成队列末尾。
            </p>
          )}
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={onCancel}>取消</Button>
          <Button onClick={() => onSave(text, prompt || null)}>保存</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
