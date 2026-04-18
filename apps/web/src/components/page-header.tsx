'use client'

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

type Ctx = {
  content: ReactNode
  setContent: (node: ReactNode) => void
}

const PageHeaderContext = createContext<Ctx | null>(null)

export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode>(null)
  return (
    <PageHeaderContext.Provider value={{ content, setContent }}>
      {children}
    </PageHeaderContext.Provider>
  )
}

export function usePageHeaderSlot() {
  const ctx = useContext(PageHeaderContext)
  if (!ctx) throw new Error('usePageHeaderSlot must be used within PageHeaderProvider')
  return ctx.content
}

export function PageHeader({ children }: { children: ReactNode }) {
  const ctx = useContext(PageHeaderContext)
  if (!ctx) throw new Error('PageHeader must be used within PageHeaderProvider')
  const { setContent } = ctx
  useEffect(() => {
    setContent(children)
    return () => setContent(null)
  }, [children, setContent])
  return null
}
