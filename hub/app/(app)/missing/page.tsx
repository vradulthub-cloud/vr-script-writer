import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Scene, type SceneStats } from "@/lib/api"

const SceneGrid = nextDynamic(() => import("./scene-grid").then(m => m.SceneGrid))

export const dynamic = "force-dynamic"

export default async function MissingPage() {
  const session = await auth()
  const client = api(session)

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

  return (
    <SceneGrid scenes={scenes} stats={stats} error={error} idToken={(session as { idToken?: string } | null)?.idToken} />
  )
}
