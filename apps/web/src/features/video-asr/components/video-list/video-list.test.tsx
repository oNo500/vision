import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VideoList } from './index'
import type { VideoItem } from '@/features/video-asr/hooks/use-videos'

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))
vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000' },
}))
vi.mock('@/config/app-paths', () => ({
  appPaths: {
    dashboard: {
      videoAsrDetail: (id: string) => ({ href: `/video-asr/${id}` }),
    },
  },
}))

const mockVideos: VideoItem[] = [
  { video_id: 'BV1abc', url: 'https://x.com', source: 'bilibili', title: '测试视频', uploader: 'UP主', duration_sec: 3661, asr_model: 'gemini', processed_at: '2026-04-19T00:00:00' },
]

describe('VideoList', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders video title', () => {
    render(<VideoList videos={mockVideos} loading={false} />)
    expect(screen.getByText('测试视频')).toBeDefined()
  })

  it('shows loading state', () => {
    render(<VideoList videos={[]} loading={true} />)
    expect(screen.getByText(/加载中/)).toBeDefined()
  })

  it('shows empty state when no videos', () => {
    render(<VideoList videos={[]} loading={false} />)
    expect(screen.getByText(/暂无视频/)).toBeDefined()
  })

  it('renders link to detail page', () => {
    render(<VideoList videos={mockVideos} loading={false} />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe('/video-asr/BV1abc')
  })
})
