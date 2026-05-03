"use server"

import { updateTag } from "next/cache"
import type { CacheTag } from "./cache-tags"

/**
 * Bust one or more dashboard cache tags after a successful mutation.
 *
 * Uses `updateTag` (Next 16) for read-your-own-writes semantics — the
 * caller just changed something and expects to see it on the next
 * render. `revalidateTag(tag, profile)` would give stale-while-revalidate,
 * which is the wrong UX here.
 *
 * Call from a client component immediately after a successful POST/PUT/
 * PATCH/DELETE. Example:
 *
 *   await client.scenes.updateTitle(id, value)
 *   await revalidateAfterWrite([TAG_SCENES])
 *
 * Failures are swallowed: if invalidation throws, the user still sees
 * their write succeed; the dashboard catches up on the TTL.
 */
export async function revalidateAfterWrite(tags: CacheTag[]): Promise<void> {
  for (const tag of tags) {
    try {
      updateTag(tag)
    } catch {
      // best-effort; nothing to surface here
    }
  }
}
