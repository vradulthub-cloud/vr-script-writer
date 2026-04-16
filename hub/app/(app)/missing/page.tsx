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
    ;[scenes, stats] = await Promise.all([
      client.scenes.list({ limit: 40, missing_only: true }),
      client.scenes.stats(),
    ])
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="tracking-tight">
          Asset Tracker
        </h1>
        <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
          {stats.missing_any} of {stats.total} scenes missing assets
        </p>
      </div>
      <SceneGrid scenes={scenes} stats={stats} error={error} idToken={(session as { idToken?: string } | null)?.idToken} />
    </div>
  )
}
