/**
 * Unit tests for useLiveStream's event reducer.
 * Exported as a pure function so we can test it without a real EventSource.
 */
import { describe, expect, it } from 'vitest'

import { applyLiveEvent, type PipelineItem } from './use-live-stream'

describe('applyLiveEvent', () => {
  it('tts_queued appends a pending item', () => {
    const next = applyLiveEvent([], {
      type: 'tts_queued',
      id: 'a',
      content: 'hi',
      speech_prompt: null,
      stage: 'pending',
      urgent: false,
      ts: 1,
    })
    expect(next).toEqual<PipelineItem[]>([
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
    ])
  })

  it('tts_synthesized promotes the matching id to synthesized', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_synthesized', id: 'a', stage: 'synthesized', ts: 2 })
    expect(next[0]?.stage).toBe('synthesized')
  })

  it('tts_playing promotes the matching id to playing', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'synthesized', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_playing', id: 'a', content: 'hi', speech_prompt: null, ts: 2 })
    expect(next[0]?.stage).toBe('playing')
  })

  it('tts_done marks the item done', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'playing', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_done', id: 'a', ts: 3 })
    expect(next[0]?.stage).toBe('done')
  })

  it('unknown event types are ignored and return the same reference', () => {
    const initial: PipelineItem[] = []
    const next = applyLiveEvent(initial, { type: 'garbage', ts: 0 })
    expect(next).toBe(initial)
  })

  it('tts_synthesized for unknown id is a no-op (returns same reference)', () => {
    const initial: PipelineItem[] = []
    const next = applyLiveEvent(initial, { type: 'tts_synthesized', id: 'nope', stage: 'synthesized', ts: 1 })
    expect(next).toBe(initial)
  })
})
