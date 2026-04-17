import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, cachedUsersMe, type UserProfile } from "@/lib/api"

const ScriptGenerator = nextDynamic(() => import("./script-generator").then(m => m.ScriptGenerator))

export const dynamic = "force-dynamic"

export default async function ScriptsPage() {
  const session = await auth()
  const client = api(session)

  let tabs: string[] = []
  let error: string | null = null
  let userProfile: UserProfile | null = null

  try {
    tabs = await client.scripts.tabs()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load script tabs"
  }

  const idToken = (session as { idToken?: string } | null)?.idToken
  try {
    userProfile = await cachedUsersMe(idToken)
  } catch (err) {
    console.error("[hub] /api/users/me failed in ScriptsPage:", err)
  }

  return (
    <ScriptGenerator
      tabs={tabs}
      tabsError={error}
      idToken={idToken}
      userRole={userProfile?.role}
    />
  )
}
