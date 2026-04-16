import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Scene } from "@/lib/api"

const CompBuilder = nextDynamic(() => import("./comp-builder").then(m => m.CompBuilder))

export const dynamic = "force-dynamic"

export default async function CompilationsPage() {
  const session = await auth()
  const client = api(session)

  let scenes: Scene[] = []
  let error: string | null = null

  try {
    scenes = await client.scenes.list({ limit: 200 })
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="tracking-tight">
          Compilation Builder
        </h1>
        <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
          Build compilation plans from existing scene library
        </p>
      </div>
      <CompBuilder
        allScenes={scenes}
        scenesError={error}
        idToken={(session as { idToken?: string } | null)?.idToken}
      />
    </div>
  )
}
