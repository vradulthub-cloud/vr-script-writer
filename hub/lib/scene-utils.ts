import type { Scene } from "@/lib/api"

/**
 * The boolean asset fields we track completeness against. Scene-grid
 * and scene-detail use different labels ("Desc" vs "Description") but
 * share these keys — keep them in one place so adding a new asset
 * doesn't silently diverge between the two views.
 */
export const ASSET_KEYS: Array<keyof Scene> = [
  "has_description",
  "has_videos",
  "has_thumbnail",
  "has_photos",
  "has_storyboard",
]

export function completionPct(scene: Scene): number {
  const present = ASSET_KEYS.filter((k) => scene[k]).length
  return Math.round((present / ASSET_KEYS.length) * 100)
}
