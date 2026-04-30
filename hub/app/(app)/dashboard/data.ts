import { cache } from "react"
import { unstable_cache } from "next/cache"
import { api, type Notification, type Scene, type SceneStats, type Script, type Shoot } from "@/lib/api"

/**
 * Two layers of caching are composed here:
 *
 * 1. `unstable_cache` (Next.js) memoizes results across requests for `revalidate`
 *    seconds and tags them so any mutation can call `revalidateTag(...)` from
 *    `lib/cache-tags.ts` to expire the entry on demand.
 *    Goal: most dashboard renders never cross the WAN to the Windows backend.
 *
 * 2. React `cache()` wraps the result of #1 so multiple sections inside a single
 *    render share the same in-flight promise (e.g. BriefingSection +
 *    CalendarSection both consume getShoots).
 *
 * The fetchers swallow backend errors and return sentinels (null / [] / false)
 * so a slow or failing endpoint collapses one section without taking down the
 * whole page. unstable_cache will not memoize a thrown error — the inner
 * try/catch keeps the cache populated with the sentinel until revalidation,
 * which is fine for a brief outage and still prompts a fresh attempt later.
 *
 * `idToken` is included as a function argument so each user's calls authorize
 * correctly. Token rotation produces fresh cache keys roughly hourly which is
 * acceptable churn — within an hour the same user shares cache entries across
 * navigations, and the underlying data is global anyway (notifications differ
 * by recipient, which the recipient's token already keys correctly).
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

// ─── revalidate windows ─────────────────────────────────────────────────────
// The sync engine pulls Sheets every 300s, so anything <300s here is bounded
// by the sync floor. We pick shorter windows than the sync to keep the cache
// fresh while still absorbing the typical user navigation burst.
const REV_FAST = 30   // notifications, health
const REV_MED  = 60   // shoots, scenes, scripts, stats — also revalidatable on write
const REV_SLOW = 120  // scene stats — global aggregate, changes slowly
// Triage feed is the user's first signal that an upload landed, so it gets
// a tighter floor than other scene reads. Manual Refresh + revalidateTag
// (see actions.ts / Phase 2) collapse the gap further on writes.
const REV_TRIAGE = 20

// Cache tags — exported as constants so mutation handlers can import and
// revalidate the right surface without typo risk.
export const TAG_SHOOTS        = "shoots"
export const TAG_SCENES        = "scenes"
export const TAG_SCENE_STATS   = "scene-stats"
export const TAG_SCRIPTS       = "scripts"
export const TAG_NOTIFICATIONS = "notifications"
export const TAG_HEALTH        = "health"

export const getSceneStats = cache(
  unstable_cache(
    async (idToken: string | undefined): Promise<SceneStats | null> => {
      try {
        return await api(idToken ?? null).scenes.stats()
      } catch {
        return null
      }
    },
    ["dashboard:scene-stats"],
    { tags: [TAG_SCENE_STATS, TAG_SCENES], revalidate: REV_SLOW },
  ),
)

export const getScripts = cache(
  unstable_cache(
    async (idToken: string | undefined): Promise<Script[]> => {
      try {
        return await api(idToken ?? null).scripts.list({ needs_script: true })
      } catch {
        return []
      }
    },
    ["dashboard:scripts-needs-script"],
    { tags: [TAG_SCRIPTS], revalidate: REV_MED },
  ),
)

export const getShoots = cache(
  unstable_cache(
    async (idToken: string | undefined): Promise<{ shoots: Shoot[]; failed: boolean }> => {
      try {
        const shoots = await api(idToken ?? null).shoots.list()
        return { shoots, failed: false }
      } catch {
        return { shoots: [], failed: true }
      }
    },
    ["dashboard:shoots"],
    { tags: [TAG_SHOOTS], revalidate: REV_MED },
  ),
)

// Triage feed shows top 5 per studio. The backend's /scenes/recent endpoint
// applies the per-studio cap server-side via UNION ALL, so one busy studio
// can't crowd the others out. Single round-trip instead of three.
const RECENT_SCENE_STUDIOS = ["FuckPassVR", "VRHush", "VRAllure"] as const

export const getRecentScenes = cache(
  unstable_cache(
    async (idToken: string | undefined): Promise<Scene[]> => {
      try {
        const result = await api(idToken ?? null).scenes.recent({
          studios: [...RECENT_SCENE_STUDIOS],
          per_studio: 5,
          missing_only: true,
        })
        // Defensive — the mock fallback returns null for unmapped paths, and
        // a partially-deployed backend without /scenes/recent would do the
        // same. Always hand the consumer an array so .filter() never crashes.
        return Array.isArray(result) ? result : []
      } catch {
        return []
      }
    },
    ["dashboard:recent-scenes"],
    { tags: [TAG_SCENES], revalidate: REV_TRIAGE },
  ),
)

export const getNotifications = cache(
  unstable_cache(
    async (idToken: string | undefined): Promise<Notification[]> => {
      try {
        return await api(idToken ?? null).notifications.list(12)
      } catch {
        return []
      }
    },
    ["dashboard:notifications-12"],
    { tags: [TAG_NOTIFICATIONS], revalidate: REV_FAST },
  ),
)

export const getHealthOk = cache(
  unstable_cache(
    async (idToken: string | undefined): Promise<boolean> => {
      try {
        await api(idToken ?? null).health()
        return true
      } catch {
        return false
      }
    },
    ["dashboard:health"],
    { tags: [TAG_HEALTH], revalidate: REV_FAST },
  ),
)
