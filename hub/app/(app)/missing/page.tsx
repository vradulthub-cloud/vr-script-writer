import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Scene, type SceneStats } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { MissingV2View } from "./missing-v2-view"

const SceneGrid = nextDynamic(() => import("./scene-grid").then(m => m.SceneGrid))

export const dynamic = "force-dynamic"

export default async function MissingPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Tickets", idToken)
  const client = api(session)

  let scenes: Scene[] = []
  let stats: SceneStats = { total: 0, by_studio: {}, complete: 0, missing_any: 0 }
  let error: string | null = null
  let sceneSyncedAt: string | null = null

  try {
    // Use the per-studio fan-out endpoint instead of `list({ limit: 20 })`.
    // VRH currently has 474 of the 538 missing scenes (88%), so a flat
    // global LIMIT 20 returns ~all VRH and the FuckPassVR/VRAllure/NJOI
    // tabs render as "all clear" even when each has missing scenes too.
    // /scenes/recent does a UNION ALL of per-studio LIMIT subqueries so
    // every studio's top-N is represented.
    const [statsResult, syncResult, scenesResult] = await Promise.allSettled([
      client.scenes.stats(),
      client.sync.status(),
      client.scenes.recent({
        studios: ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"],
        per_studio: 5,
        missing_only: true,
      }),
    ])
    if (statsResult.status === "fulfilled") stats = statsResult.value
    else error = "Failed to load scenes"
    if (syncResult.status === "fulfilled") {
      const sceneSync = syncResult.value.find(s => s.source === "scenes")
      sceneSyncedAt = sceneSync?.last_synced_at ?? null
    }
    scenes = scenesResult.status === "fulfilled" ? scenesResult.value : []
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  return (
    <div>
      <MissingV2View stats={stats} scenes={scenes} fetchFailed={error !== null} sceneSyncedAt={sceneSyncedAt} />
      <div className="ec-embed-grid">
        <SceneGrid scenes={scenes} stats={stats} error={error} idToken={idToken} />
      </div>
    </div>
  )
}
