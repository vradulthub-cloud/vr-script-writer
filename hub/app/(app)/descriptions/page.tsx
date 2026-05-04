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
    // `missing_descriptions` is a targeted backend filter that returns only
    // scenes that are actually missing a description — no client-side filtering
    // needed, and no artificial limit required.
    scenes = await client.scenes.list({ missing_descriptions: true, limit: 2000 })
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
