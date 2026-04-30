/**
 * Single source of truth for the cache tags used by the dashboard's
 * `unstable_cache` entries. Anything that mutates server state should
 * pass the right subset of these to `revalidateAfterWrite()` from
 * `lib/cache-actions.ts` so the dashboard reflects the change on the
 * next render instead of waiting out the TTL.
 *
 * Pure constants — no `"use server"` here so this module can be imported
 * from server components, server actions, and (read-only) from client
 * components alike.
 */

export const TAG_SHOOTS        = "shoots"
export const TAG_SCENES        = "scenes"
export const TAG_SCENE_STATS   = "scene-stats"
export const TAG_SCRIPTS       = "scripts"
export const TAG_NOTIFICATIONS = "notifications"
export const TAG_HEALTH        = "health"

export type CacheTag =
  | typeof TAG_SHOOTS
  | typeof TAG_SCENES
  | typeof TAG_SCENE_STATS
  | typeof TAG_SCRIPTS
  | typeof TAG_NOTIFICATIONS
  | typeof TAG_HEALTH
