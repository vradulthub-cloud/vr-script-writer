"use client"

import { useEffect, useState } from "react"
import { TodayBriefing, type Briefing } from "@/components/ui/today-briefing"

const STORAGE_KEY = "eclatech:briefing-cache"
const MAX_AGE_MS  = 24 * 60 * 60 * 1000 // 24 h — stale past this

interface CacheEntry {
  briefing: Briefing
  savedAt:  number
}

function relativeTime(ms: number): string {
  const s = Math.floor((Date.now() - ms) / 1000)
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

/**
 * Client shell around TodayBriefing.
 *
 * When the server briefing is fresh (non-error): persists it to localStorage.
 * When the server briefing is an error state: attempts to restore the last
 * good briefing from cache and surfaces it with a "Cached · Xm ago" notice.
 * Falls back to the error briefing if cache is absent or expired.
 */
export function BriefingCache({ briefing }: { briefing: Briefing }) {
  const [displayed, setDisplayed] = useState<Briefing>(briefing)
  const [cachedAt,  setCachedAt]  = useState<number | null>(null)

  useEffect(() => {
    if (briefing.tone !== "error") {
      // Fresh data — persist it, display as-is.
      try {
        const entry: CacheEntry = { briefing, savedAt: Date.now() }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entry))
      } catch { /* storage quota / private browsing */ }
      return
    }

    // Error state — try the cache.
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const entry: CacheEntry = JSON.parse(raw)
      if (Date.now() - entry.savedAt > MAX_AGE_MS) return
      setDisplayed(entry.briefing)
      setCachedAt(entry.savedAt)
    } catch { /* corrupt entry */ }
  }, [briefing])

  return <TodayBriefing briefing={displayed} cachedAt={cachedAt} />
}
