import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, cachedUsersMe, type Scene, type UserProfile } from "@/lib/api"

const DescGenerator = nextDynamic(() => import("./desc-generator").then(m => m.DescGenerator))

export const dynamic = "force-dynamic"

export default async function DescriptionsPage() {
  const session = await auth()
  const client = api(session)

  let scenes: Scene[] = []
  let error: string | null = null
  let userProfile: UserProfile | null = null

  try {
    scenes = await client.scenes.list({ limit: 100 })
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  const idToken = (session as { idToken?: string } | null)?.idToken
  try {
    userProfile = await cachedUsersMe(idToken)
  } catch (err) {
    console.error("[hub] /api/users/me failed in DescriptionsPage:", err)
  }

  return (
    <DescGenerator
      scenes={scenes}
      scenesError={error}
      idToken={idToken}
      userRole={userProfile?.role}
    />
  )
}
