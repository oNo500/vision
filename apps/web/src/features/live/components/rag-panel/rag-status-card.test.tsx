import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { RagStatus } from '@/features/live/hooks/use-rag-library'

import { RagStatusCard } from './rag-status-card'

const base: RagStatus = {
  indexed: false,
  dirty: false,
  chunk_count: 0,
  build_time: null,
  file_count: 0,
  sources: [],
}

describe('RagStatusCard', () => {
  it('shows placeholder for never-built index', () => {
    render(<RagStatusCard status={base} />)
    expect(screen.getByText('从未构建')).toBeInTheDocument()
    expect(screen.getByText('未构建')).toBeInTheDocument()
  })

  it('shows counts and indexed state', () => {
    render(
      <RagStatusCard
        status={{
          ...base,
          indexed: true,
          chunk_count: 42,
          file_count: 7,
          build_time: '2026-04-18T12:00:00Z',
        }}
      />,
    )
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('已同步')).toBeInTheDocument()
  })

  it('flags dirty state in warning tone', () => {
    render(
      <RagStatusCard status={{ ...base, indexed: true, dirty: true, file_count: 3 }} />,
    )
    expect(screen.getByText('有未索引变更')).toBeInTheDocument()
  })
})
