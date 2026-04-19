'use client'

import { useState } from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@workspace/ui/components/sheet'
import { Button } from '@workspace/ui/components/button'
import { Label } from '@workspace/ui/components/label'

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
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex flex-col gap-0 p-0 sm:max-w-lg">
        <SheetHeader className="border-b px-6 py-5">
          <SheetTitle>新建转录任务</SheetTitle>
          <SheetDescription>支持 B 站、YouTube 等平台链接</SheetDescription>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-5">
          <div className="flex flex-col gap-2">
            <Label htmlFor="urls">视频 URL</Label>
            <textarea
              id="urls"
              className="min-h-[180px] w-full resize-none rounded-md border border-input bg-background px-3 py-2.5 text-sm leading-relaxed placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder={"https://www.bilibili.com/video/BV...\nhttps://www.youtube.com/watch?v=..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              每行一个链接{urls.length > 0 ? `，已输入 ${urls.length} 个` : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t px-6 py-4">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            取消
          </Button>
          <Button disabled={urls.length === 0 || submitting} onClick={handleSubmit}>
            {submitting ? '提交中...' : `提交${urls.length > 1 ? ` (${urls.length})` : ''}`}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
