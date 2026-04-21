import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Scene, type SceneStats } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { MissingV2View } from "./missing-v2-view"

const SceneGrid = nextDynamic(() => import("./scene-grid").then(m => m.SceneGrid))

export const dynamic = "force-dynamic"

export default async function MissingPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Tickets", idToken)
  const client = api(session)
  const v2 = await isEclatechV2()

  let scenes: Scene[] = []
  let stats: SceneStats = { total: 0, by_studio: {}, complete: 0, missing_any: 0 }
  let error: string | null = null

  try {
    const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]
    const [statsResult, ...studioResults] = await Promise.all([
      client.scenes.stats(),
      ...STUDIOS.map(s => client.scenes.list({ studio: s, limit: 5, missing_only: true })),
    ])
    stats = statsResult
    scenes = studioResults.flat()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  if (v2) {
    return (
      <div>
        <MissingV2View stats={stats} />
        <SceneGrid scenes={scenes} stats={stats} error={error} idToken={idToken} />
      </div>
    )
  }

  return (
    <SceneGrid scenes={scenes} stats={stats} error={error} idToken={idToken} />
  )
}
