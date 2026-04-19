import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { RagSource } from '@/features/live/hooks/use-rag-library'

import { FileList } from './file-list'

const sources: RagSource[] = [
  { rel_path: 'scripts/opening.md', category: 'scripts',
    chunks: 4, sha256: 'a', indexed: true },
  { rel_path: 'scripts/dirty.md', category: 'scripts',
    chunks: 0, sha256: 'b', indexed: false },
  { rel_path: 'product_manual/spec.md', category: 'product_manual',
    chunks: 6, sha256: 'c', indexed: true },
]

describe('FileList', () => {
  it('groups files by category and shows chunk counts', () => {
    render(<FileList sources={sources} onDelete={vi.fn()} />)
    expect(screen.getByText('opening.md')).toBeInTheDocument()
    expect(screen.getByText('spec.md')).toBeInTheDocument()
    expect(screen.getByText('4 chunks')).toBeInTheDocument()
    expect(screen.getByText('6 chunks')).toBeInTheDocument()
  })

  it('marks unindexed files as 待索引', () => {
    render(<FileList sources={sources} onDelete={vi.fn()} />)
    expect(screen.getByText('待索引')).toBeInTheDocument()
  })

  it('shows empty state when no sources', () => {
    render(<FileList sources={[]} onDelete={vi.fn()} />)
    expect(screen.getByText(/尚未上传/)).toBeInTheDocument()
  })

  it('confirms before calling onDelete', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn().mockResolvedValue(true)
    render(<FileList sources={sources} onDelete={onDelete} />)

    const deleteButtons = screen.getAllByRole('button', { name: '删除' })
    await user.click(deleteButtons[0]!)

    // Dialog appears with two buttons (取消 / 删除)
    expect(screen.getByText(/确认删除/)).toBeInTheDocument()

    // Find the confirm button inside the dialog (destructive variant)
    const confirmButtons = screen.getAllByRole('button', { name: '删除' })
    // The last 删除 is the confirm button in the dialog
    await user.click(confirmButtons[confirmButtons.length - 1]!)

    expect(onDelete).toHaveBeenCalledWith('scripts', 'opening.md')
  })

  it('cancel dialog does not call onDelete', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    render(<FileList sources={sources} onDelete={onDelete} />)

    await user.click(screen.getAllByRole('button', { name: '删除' })[0]!)
    await user.click(screen.getByRole('button', { name: '取消' }))

    expect(onDelete).not.toHaveBeenCalled()
  })
})
