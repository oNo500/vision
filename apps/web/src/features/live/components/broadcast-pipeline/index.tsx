'use client'

import { LayoutGroup } from 'motion/react'

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
  const { remove, edit, reorder: reorderApi } = useTtsMutations()

  const onRemove = (id: string) => { void remove(id) }
  const onEdit = (id: string, text: string, speech_prompt: string | null) => {
    void edit(id, { text, speech_prompt })
  }
  const onReorder = (stage: 'pending' | 'synthesized', newIds: string[]) => {
    void reorderApi(stage, newIds)
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
      <LayoutGroup>
        {/* Fixed-row layout so operating on one stage doesn't shift others */}
        <div className="flex min-h-0 flex-1 flex-col">
          <StageSection
            title="待合成"
            stage="pending"
            items={pending}
            onRemove={onRemove}
            onEdit={onEdit}
            onReorder={onReorder}
            listHeight={360}
          />
          <StageSection
            title="已合成"
            stage="synthesized"
            items={synthesized}
            onRemove={onRemove}
            onEdit={onEdit}
            onReorder={onReorder}
            listHeight={210}
          />
          <NowPlayingCard item={nowPlayingItem} />
          <div className="min-h-0 flex-1 overflow-auto">
            <HistorySection items={history} />
          </div>
        </div>
      </LayoutGroup>
    </div>
  )
}
