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

  // The initial scenes payload powers the grid before the user touches the
  // "Per studio" dropdown. A flat `limit: 20` here would order by id DESC
  // and skew the entire grid to VRH/VRA (their prefixes sort highest in
  // ASCII), so FPVR and NJOI rows wouldn't appear at all on first load.
  // Fan out per studio to mirror what the dropdown does — the page already
  // knows about exactly four studios.
  const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]
  try {
    const [statsResult, syncResult, ...studioResults] = await Promise.allSettled([
      client.scenes.stats(),
      client.sync.status(),
      ...STUDIOS.map(s => client.scenes.list({ studio: s, limit: 5, missing_only: true })),
    ])
    if (statsResult.status === "fulfilled") stats = statsResult.value
    else error = "Failed to load scenes"
    if (syncResult.status === "fulfilled") {
      const sceneSync = syncResult.value.find(s => s.source === "scenes")
      sceneSyncedAt = sceneSync?.last_synced_at ?? null
    }
    scenes = studioResults.flatMap(r => (r.status === "fulfilled" ? r.value : []))
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
