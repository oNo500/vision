import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PlanRagLibraries } from './plan-rag-libraries'

vi.mock('@workspace/ui/components/sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api-fetch', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

const mockUseRagLibraries = vi.fn()
vi.mock('@/features/live/hooks/use-rag-libraries', () => ({
  useRagLibraries: () => mockUseRagLibraries(),
}))

function ok<T>(data: T) { return { ok: true as const, data, status: 200 } }

const libs = [
  { id: 'lib-a', name: 'Library A', created_at: '' },
  { id: 'lib-b', name: 'Library B', created_at: '' },
]

describe('PlanRagLibraries', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseRagLibraries.mockReturnValue({ libraries: libs })
  })

  it('shows empty state when no libraries exist', async () => {
    mockUseRagLibraries.mockReturnValue({ libraries: [] })
    mockApiFetch.mockResolvedValueOnce(ok({ rag_library_ids: [] }))
    render(<PlanRagLibraries planId="plan-1" />)
    expect(screen.getByText(/暂无素材库/)).toBeTruthy()
  })

  it('renders checkboxes for each library', async () => {
    mockApiFetch.mockResolvedValueOnce(ok({ rag_library_ids: ['lib-a'] }))
    render(<PlanRagLibraries planId="plan-1" />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes).toHaveLength(2)
    })
  })

  it('pre-checks libraries from plan rag_library_ids', async () => {
    mockApiFetch.mockResolvedValueOnce(ok({ rag_library_ids: ['lib-a'] }))
    render(<PlanRagLibraries planId="plan-1" />)
    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
      expect(checkboxes[0].checked).toBe(true)
      expect(checkboxes[1].checked).toBe(false)
    })
  })

  it('calls PUT endpoint with selected library ids on save', async () => {
    mockApiFetch
      .mockResolvedValueOnce(ok({ rag_library_ids: [] }))
      .mockResolvedValueOnce(ok({ rag_library_ids: ['lib-a'] }))
    render(<PlanRagLibraries planId="plan-1" />)
    await waitFor(() => screen.getAllByRole('checkbox'))

    fireEvent.click(screen.getAllByRole('checkbox')[0])
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(
        'live/plans/plan-1/rag-libraries',
        expect.objectContaining({ method: 'PUT', body: { library_ids: ['lib-a'] } }),
      )
    })
  })
})
