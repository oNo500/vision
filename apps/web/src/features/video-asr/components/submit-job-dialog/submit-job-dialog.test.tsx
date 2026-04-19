import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SubmitJobDialog } from './index'

vi.mock('@/config/env', () => ({
  env: { NEXT_PUBLIC_API_URL: 'http://localhost:8000', NEXT_PUBLIC_API_KEY: '' },
}))

describe('SubmitJobDialog', () => {
  afterEach(() => vi.clearAllMocks())

  it('calls onSubmit with parsed URLs', async () => {
    const onSubmit = vi.fn().mockResolvedValue('job-1')
    render(
      <SubmitJobDialog open onOpenChange={() => {}} onSubmit={onSubmit} submitting={false} />
    )
    const textarea = screen.getByPlaceholderText(/URL/)
    fireEvent.change(textarea, {
      target: { value: 'https://www.bilibili.com/video/BV1abc\nhttps://www.bilibili.com/video/BV2def' },
    })
    fireEvent.click(screen.getByRole('button', { name: /提交/ }))
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith([
        'https://www.bilibili.com/video/BV1abc',
        'https://www.bilibili.com/video/BV2def',
      ])
    )
  })

  it('disables submit when input is empty', () => {
    render(
      <SubmitJobDialog open onOpenChange={() => {}} onSubmit={vi.fn()} submitting={false} />
    )
    const submitBtn = screen.getAllByRole('button').find((b) => b.textContent?.includes('提交'))
    expect(submitBtn).toBeDefined()
    expect(submitBtn).toBeDisabled()
  })

  it('disables submit when submitting=true', () => {
    render(
      <SubmitJobDialog open onOpenChange={() => {}} onSubmit={vi.fn()} submitting={true} />
    )
    // input has a URL so normally enabled, but submitting=true disables it
    const textarea = screen.getByPlaceholderText(/URL/)
    fireEvent.change(textarea, { target: { value: 'https://example.com' } })
    const submitBtn = screen.getAllByRole('button').find((b) => b.textContent?.includes('提交中'))
    expect(submitBtn).toBeDisabled()
  })
})
