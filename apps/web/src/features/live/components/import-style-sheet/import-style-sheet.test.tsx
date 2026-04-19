import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))
vi.mock('@workspace/ui/components/sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({ apiFetch: (...args: unknown[]) => mockApiFetch(...args) }))

import { ImportStyleSheet } from './index'

const videos = [
  { video_id: 'BV1abc', title: '测试视频', source: 'bilibili', duration_sec: 240 },
]

describe('ImportStyleSheet', () => {
  afterEach(() => vi.clearAllMocks())

  it('shows video list when open', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
    render(
      <ImportStyleSheet open onOpenChange={vi.fn()} onImport={vi.fn()} />
    )
    await waitFor(() => expect(screen.getByText('测试视频')).toBeDefined())
  })

  it('calls onImport with video_id when button clicked', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
    const onImport = vi.fn().mockResolvedValue(true)
    render(
      <ImportStyleSheet open onOpenChange={vi.fn()} onImport={onImport} />
    )
    await waitFor(() => screen.getByText('测试视频'))
    fireEvent.click(screen.getByRole('button', { name: '导入' }))
    await waitFor(() => expect(onImport).toHaveBeenCalledWith('BV1abc'))
  })

  it('closes sheet after successful import', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: true, data: videos, status: 200 })
    const onOpenChange = vi.fn()
    const onImport = vi.fn().mockResolvedValue(true)
    render(
      <ImportStyleSheet open onOpenChange={onOpenChange} onImport={onImport} />
    )
    await waitFor(() => screen.getByText('测试视频'))
    fireEvent.click(screen.getByRole('button', { name: '导入' }))
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
  })
})
