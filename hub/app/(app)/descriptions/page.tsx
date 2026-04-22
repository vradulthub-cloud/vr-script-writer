import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Scene } from "@/lib/api"
import { requireTab } from "@/lib/rbac"

const DescGenerator = nextDynamic(() => import("./desc-generator").then(m => m.DescGenerator))

export const dynamic = "force-dynamic"

export default async function DescriptionsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const userProfile = await requireTab("Descriptions", idToken)
  const client = api(session)

  let scenes: Scene[] = []
  let error: string | null = null

  try {
    // `missing_only` narrows to scenes missing at least one core asset
    // (description, videos, thumbnail, photos, storyboard). The queue in
    // DescGenerator then filters locally to the ones still lacking a
    // description. Without missing_only + a high limit, scenes that need
    // descriptions get buried past the first 100 rows sorted by id DESC —
    // which is exactly the "no new scenes show up" bug we hit on 2026-04-21.
    scenes = await client.scenes.list({ limit: 500, missing_only: true })
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  return (
    <DescGenerator
      scenes={scenes}
      scenesError={error}
      idToken={idToken}
      userRole={userProfile.role}
    />
  )
}
