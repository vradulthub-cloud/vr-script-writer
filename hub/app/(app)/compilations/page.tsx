import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Scene } from "@/lib/api"
import { requireTab } from "@/lib/rbac"

const CompBuilder = nextDynamic(() => import("./comp-builder").then(m => m.CompBuilder))

export const dynamic = "force-dynamic"

export default async function CompilationsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Compilations", idToken)
  const client = api(session)

  let scenes: Scene[] = []
  let error: string | null = null

  try {
    scenes = await client.scenes.list({ limit: 200 })
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  return (
    <CompBuilder
      allScenes={scenes}
      scenesError={error}
      idToken={idToken}
    />
  )
}
