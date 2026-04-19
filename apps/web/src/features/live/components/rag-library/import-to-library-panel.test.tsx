import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))
vi.mock('@workspace/ui/components/sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({ apiFetch: (...args: unknown[]) => mockApiFetch(...args) }))

import { ImportToLibraryPanel } from './import-to-library-panel'

const libraries = [
  { id: 'lib-a', name: '素材库A', created_at: '' },
]
const videos = [
  { video_id: 'BV1abc', title: '测试视频', source: 'bilibili', duration_sec: 240 },
]

describe('ImportToLibraryPanel', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders library selector', () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: libraries, status: 200 })
    render(<ImportToLibraryPanel />)
    // wait for libraries to load
    return waitFor(() => expect(screen.getByText('素材库A')).toBeDefined())
  })

  it('shows video list after library selected', async () => {
    mockApiFetch
      .mockResolvedValueOnce({ ok: true, data: libraries, status: 200 })
      .mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
      .mockResolvedValue({ ok: false, data: null, status: 500 })
    render(<ImportToLibraryPanel />)
    await waitFor(() => screen.getByText('素材库A'))
    fireEvent.click(screen.getByText('素材库A'))
    await waitFor(() => expect(screen.getByText('测试视频')).toBeDefined())
  })

  it('shows empty message when no libraries', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: [], status: 200 })
    render(<ImportToLibraryPanel />)
    await waitFor(() => expect(screen.getByText('暂无素材库，请先在「素材库」页面创建。')).toBeDefined())
  })
})
