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
    // The backend defaults to LIMIT 50 and ORDER BY id DESC. Scene IDs prefixed
    // VRH/VRA sort above FPVR/NNJOI in ASCII, so without an explicit limit the
    // page only ever sees VRH scenes — the studio selector below would render
    // empty for FPVR/VRA/NJOI even when they have plenty of missing rows. Ask
    // for the backend max so the studio split downstream sees every studio.
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
