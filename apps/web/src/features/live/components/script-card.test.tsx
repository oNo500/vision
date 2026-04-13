import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ScriptState } from '../hooks/use-live-stream'
import { ScriptCard } from './script-card'

vi.mock('@/config/env', () => ({
  env: {
    NEXT_PUBLIC_API_URL: 'http://localhost:8000',
  },
}))

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn() },
}))

const mockScriptState: ScriptState = {
  segment_id: 'seg-01',
  title: '产品介绍',
  goal: '重点讲解产品卖点',
  cue: ['益生菌修护屏障'],
  must_say: false,
  remaining_seconds: 30,
  segment_duration: 60,
  finished: false,
}

describe('ScriptCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
  })

  it('renders "未开始" when scriptState is null', () => {
    render(<ScriptCard scriptState={null} running={false} />)
    expect(screen.getByText('未开始')).toBeInTheDocument()
  })

  it('renders segment_id badge when scriptState has a segment_id', () => {
    render(<ScriptCard scriptState={mockScriptState} running={true} />)
    expect(screen.getByText('seg-01')).toBeInTheDocument()
  })

  it('buttons are disabled when running is false', () => {
    render(<ScriptCard scriptState={mockScriptState} running={false} />)
    const buttons = screen.getAllByRole('button')
    for (const button of buttons) {
      expect(button).toBeDisabled()
    }
  })

  it('buttons are enabled when running is true and loading is false', () => {
    render(<ScriptCard scriptState={mockScriptState} running={true} />)
    const buttons = screen.getAllByRole('button')
    for (const button of buttons) {
      expect(button).not.toBeDisabled()
    }
  })

  it('progress bar width is "0%" when scriptState is null', () => {
    const { container } = render(<ScriptCard scriptState={null} running={false} />)
    const progressBar = container.querySelector('.bg-primary')
    expect(progressBar).toHaveStyle({ width: '0%' })
  })

  it('calls fetch with POST to correct URL when next button clicked', async () => {
    const user = userEvent.setup()
    render(<ScriptCard scriptState={mockScriptState} running={true} />)
    const nextButton = screen.getByRole('button', { name: /下一段/ })
    await user.click(nextButton)
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/live/script/next',
      { method: 'POST' },
    )
  })

  it('shows error toast when script navigation fails with non-ok response', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    const user = userEvent.setup()

    vi.mocked(fetch).mockResolvedValue({ ok: false } as Response)

    render(<ScriptCard scriptState={mockScriptState} running={true} />)
    const nextButton = screen.getByRole('button', { name: /下一段/ })
    await user.click(nextButton)

    expect(toast.error).toHaveBeenCalledOnce()
  })

  it('shows error toast when script navigation throws (network error)', async () => {
    const { toast } = await import('@workspace/ui/components/sonner')
    const user = userEvent.setup()

    vi.mocked(fetch).mockRejectedValue(new Error('Network error'))

    render(<ScriptCard scriptState={mockScriptState} running={true} />)
    const prevButton = screen.getByRole('button', { name: /上一段/ })
    await user.click(prevButton)

    expect(toast.error).toHaveBeenCalledOnce()
  })
})
