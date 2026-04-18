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

  it('tts_removed filters out the matching id', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'hi', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
      { id: 'b', content: 'ho', speech_prompt: null, stage: 'pending', urgent: false, ts: 2 },
    ]
    const next = applyLiveEvent(initial, { type: 'tts_removed', id: 'a', stage: 'pending', ts: 3 })
    expect(next).toHaveLength(1)
    expect(next[0]?.id).toBe('b')
  })

  it('tts_edited in-place updates content and speech_prompt when id == new_id', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'old', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
    ]
    const next = applyLiveEvent(initial, {
      type: 'tts_edited', id: 'a', new_id: 'a',
      content: 'new', speech_prompt: 'prompt', stage: 'pending', ts: 2,
    })
    expect(next[0]?.content).toBe('new')
    expect(next[0]?.speech_prompt).toBe('prompt')
  })

  it('tts_edited with id swap retires old and appends new pending', () => {
    const initial: PipelineItem[] = [
      { id: 'old', content: 'was-pcm', speech_prompt: null, stage: 'synthesized', urgent: true, ts: 1 },
    ]
    const next = applyLiveEvent(initial, {
      type: 'tts_edited', id: 'old', new_id: 'fresh',
      content: 'rewritten', speech_prompt: null, stage: 'pending', ts: 2,
    })
    expect(next.find((p) => p.id === 'old')).toBeUndefined()
    const fresh = next.find((p) => p.id === 'fresh')
    expect(fresh).toBeDefined()
    expect(fresh?.stage).toBe('pending')
    expect(fresh?.content).toBe('rewritten')
  })

  it('tts_reordered rearranges items within a stage while preserving other stages', () => {
    const initial: PipelineItem[] = [
      { id: 'a', content: 'A', speech_prompt: null, stage: 'pending', urgent: false, ts: 1 },
      { id: 'b', content: 'B', speech_prompt: null, stage: 'pending', urgent: false, ts: 2 },
      { id: 'c', content: 'C', speech_prompt: null, stage: 'synthesized', urgent: false, ts: 3 },
    ]
    const next = applyLiveEvent(initial, {
      type: 'tts_reordered', stage: 'pending', ids: ['b', 'a'], ts: 4,
    })
    const pending = next.filter((p) => p.stage === 'pending').map((p) => p.id)
    expect(pending).toEqual(['b', 'a'])
    const synth = next.filter((p) => p.stage === 'synthesized')
    expect(synth).toHaveLength(1)
    expect(synth[0]?.id).toBe('c')
  })
})
