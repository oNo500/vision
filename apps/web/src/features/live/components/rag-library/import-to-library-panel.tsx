'use client'

import { useState } from 'react'

import { useRagLibraries } from '@/features/live/hooks/use-rag-libraries'
import { useRagLibrary } from '@/features/live/hooks/use-rag-library'

import { ImportTranscriptTab } from './import-transcript-tab'

export function ImportToLibraryPanel() {
  const { libraries } = useRagLibraries()
  const [selectedLibId, setSelectedLibId] = useState<string | null>(null)

  if (libraries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        暂无素材库，请先在「素材库」页面创建。
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {libraries.map((lib) => (
          <button
            key={lib.id}
            type="button"
            onClick={() => setSelectedLibId(lib.id)}
            className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
              selectedLibId === lib.id
                ? 'border-foreground bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {lib.name}
          </button>
        ))}
      </div>

      {selectedLibId && <LibraryImporter libId={selectedLibId} />}
    </div>
  )
}

function LibraryImporter({ libId }: { libId: string }) {
  const { importTranscript } = useRagLibrary(libId)
  return <ImportTranscriptTab onImport={importTranscript} />
}
