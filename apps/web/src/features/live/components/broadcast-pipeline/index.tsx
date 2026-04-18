'use client'

import type { PipelineItem } from '@/features/live/hooks/use-live-stream'
import { useTtsMutations } from '@/features/live/hooks/use-tts-mutations'

import { HistorySection } from './history-section'
import { NowPlayingCard } from './now-playing-card'
import { PipelineHeader } from './pipeline-header'
import { StageSection } from './stage-section'

type Props = {
  pending: PipelineItem[]
  synthesized: PipelineItem[]
  nowPlayingItem: PipelineItem | null
  history: PipelineItem[]
  llmGenerating: boolean
  ttsSpeaking: boolean
  urgentCount: number
}

export function BroadcastPipeline({
  pending, synthesized, nowPlayingItem, history,
  llmGenerating, ttsSpeaking, urgentCount,
}: Props) {
  const { remove, edit } = useTtsMutations()

  const onRemove = (id: string) => { void remove(id) }
  const onEdit = (id: string, text: string, speech_prompt: string | null) => {
    void edit(id, { text, speech_prompt })
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-background">
      <PipelineHeader
        llmGenerating={llmGenerating}
        ttsSpeaking={ttsSpeaking}
        pendingCount={pending.length}
        synthesizedCount={synthesized.length}
        urgentCount={urgentCount}
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-auto">
        <StageSection title="待合成" items={pending} onRemove={onRemove} onEdit={onEdit} />
        <StageSection title="已合成" items={synthesized} onRemove={onRemove} onEdit={onEdit} />
        <NowPlayingCard item={nowPlayingItem} />
        <HistorySection items={history} />
      </div>
    </div>
  )
}
