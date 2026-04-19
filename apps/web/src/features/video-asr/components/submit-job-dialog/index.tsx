'use client'

import { useState } from 'react'
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@workspace/ui/components/sheet'
import { Button } from '@workspace/ui/components/button'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (urls: string[]) => Promise<string | null>
  submitting: boolean
}

export function SubmitJobDialog({ open, onOpenChange, onSubmit, submitting }: Props) {
  const [input, setInput] = useState('')

  const urls = input
    .split('\n')
    .map((u) => u.trim())
    .filter(Boolean)

  async function handleSubmit() {
    const jobId = await onSubmit(urls)
    if (jobId) {
      setInput('')
      onOpenChange(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={(isOpen) => onOpenChange(isOpen)}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>提交视频转录任务</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-3 py-4">
          <textarea
            className="min-h-[150px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="每行一个 URL，支持 B 站、YouTube"
            rows={6}
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">{urls.length} 个 URL</p>
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={urls.length === 0 || submitting} onClick={handleSubmit}>
            {submitting ? '提交中...' : '提交'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
