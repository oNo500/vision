'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

const BOTTOM_THRESHOLD = 50

export function useScrollAnchor() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [unread, setUnread] = useState(0)

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
    isAtBottomRef.current = true
    setIsAtBottom(true)
    setUnread(0)
  }, [])

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_THRESHOLD
    isAtBottomRef.current = atBottom
    setIsAtBottom(atBottom)
    if (atBottom) setUnread(0)
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.addEventListener('scroll', handleScroll, { passive: true })
    return () => el.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  // read ref instead of state — stable across renders, no re-creation
  const onNewMessage = useCallback(() => {
    if (isAtBottomRef.current) {
      scrollToBottom('instant')
    } else {
      setUnread((n) => n + 1)
    }
  }, [scrollToBottom])

  return { scrollRef, isAtBottom, unread, scrollToBottom, onNewMessage }
}
