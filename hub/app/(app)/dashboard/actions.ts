"use server"

import { auth } from "@/auth"
import { api } from "@/lib/api"
import { revalidateAfterWrite } from "@/lib/cache-actions"
import { TAG_SCENES, TAG_SCENE_STATS } from "@/lib/cache-tags"

/**
 * Two-step refresh because a single server action would have to sleep ~60s
 * (the time scan_mega.py needs to rebuild mega_scan.json) and Vercel's
 * function timeout would kill it. Instead the client orchestrates:
 *
 *   1. triggerMegaRefresh() — POSTs /scenes/mega-refresh; backend kicks off
 *      a background thread and returns immediately.
 *   2. Client counts down ~60s.
 *   3. revalidateRecentActivity() — uses updateTag (read-your-own-writes
 *      semantics, server-action only) to expire the cache for the user's
 *      next render. We pick updateTag over revalidateTag because the user
 *      just waited a minute and explicitly asked to see fresh data, so
 *      stale-while-revalidate would be the wrong UX.
 */

export async function triggerMegaRefresh(): Promise<{
  ok: boolean
  message: string
}> {
  const session = await auth()
  try {
    const result = await api(session).scenes.megaRefresh()
    return { ok: true, message: result.message ?? "MEGA scan started" }
  } catch (err) {
    return {
      ok: false,
      message: err instanceof Error ? err.message : "Refresh failed",
    }
  }
}

export async function revalidateRecentActivity(): Promise<void> {
  await revalidateAfterWrite([TAG_SCENES, TAG_SCENE_STATS])
}
