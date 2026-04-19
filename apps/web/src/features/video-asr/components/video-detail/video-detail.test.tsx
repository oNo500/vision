import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VideoDetail } from './index'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/features/video-asr/hooks/use-video-progress', () => ({
  useVideoProgress: () => ({
    stages: [],
    transcribeProgress: { done: 0, total: null, chunks: [], retrying: [] },
    costUsd: 0,
    finished: true,
    connected: false,
  }),
}))
vi.mock('@/features/video-asr/hooks/use-video-detail', () => ({
  useVideoDetail: () => ({
    meta: {
      video_id: 'BV1abc',
      title: '测试视频',
      uploader: 'UP主',
      source: 'bilibili',
      duration_sec: 120,
      url: 'https://x.com',
      asr_model: 'gemini',
      processed_at: '',
    },
    transcriptMd: '## 转录内容\n这是转录',
    summaryMd: '## 摘要内容\n这是摘要',
    loading: false,
  }),
}))

describe('VideoDetail', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders video title', () => {
    render(<VideoDetail videoId="BV1abc" />)
    expect(screen.getByText('测试视频')).toBeDefined()
  })

  it('renders transcript content by default', () => {
    render(<VideoDetail videoId="BV1abc" />)
    expect(screen.getByText(/转录内容/)).toBeDefined()
  })
})
