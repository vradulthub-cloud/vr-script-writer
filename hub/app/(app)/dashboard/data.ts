import { cache } from "react"
import { api, type Notification, type Scene, type SceneStats, type Script, type Shoot } from "@/lib/api"

/**
 * React `cache()` dedupes within a single render. Several dashboard sections
 * need the same payload (the briefing computes from shoots + stats + scripts;
 * the calendar and strip use shoots and stats independently), so wrapping the
 * fetchers here means each backend endpoint hits at most once per request.
 *
 * Each fetcher swallows errors and returns a sentinel (null / [] / false-ish)
 * so a slow or failing backend collapses one section without taking down the
 * whole page. The slowest section's failure is bounded to its Suspense block.
 */

export interface DashboardData {
  sceneStats: SceneStats | null
  scripts: Script[]
  shoots: Shoot[]
  shootsFetchFailed: boolean
  recentScenes: Scene[]
  notifications: Notification[]
  systemOk: boolean
}

export const getSceneStats = cache(async (idToken: string | undefined): Promise<SceneStats | null> => {
  try {
    return await api(idToken ?? null).scenes.stats()
  } catch {
    return null
  }
})

export const getScripts = cache(async (idToken: string | undefined): Promise<Script[]> => {
  try {
    return await api(idToken ?? null).scripts.list({ needs_script: true })
  } catch {
    return []
  }
})

export const getShoots = cache(async (
  idToken: string | undefined,
): Promise<{ shoots: Shoot[]; failed: boolean }> => {
  try {
    const shoots = await api(idToken ?? null).shoots.list()
    return { shoots, failed: false }
  } catch {
    return { shoots: [], failed: true }
  }
})

// Fetch per-studio so a studio with heavier recent activity (e.g. VRH) can't
// crowd FPVR / VRA out of a global limit. Triage feed shows top 5 per studio.
const RECENT_SCENE_STUDIOS = ["FuckPassVR", "VRHush", "VRAllure"] as const

export const getRecentScenes = cache(async (idToken: string | undefined): Promise<Scene[]> => {
  const client = api(idToken ?? null)
  const results = await Promise.all(
    RECENT_SCENE_STUDIOS.map(studio =>
      client.scenes.list({ studio, limit: 5, missing_only: true }).catch(() => [] as Scene[])
    )
  )
  return results.flat()
})

export const getNotifications = cache(async (idToken: string | undefined): Promise<Notification[]> => {
  try {
    return await api(idToken ?? null).notifications.list(12)
  } catch {
    return []
  }
})

export const getHealthOk = cache(async (idToken: string | undefined): Promise<boolean> => {
  try {
    await api(idToken ?? null).health()
    return true
  } catch {
    return false
  }
})
