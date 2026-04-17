import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api } from "@/lib/api"
import { requireTab } from "@/lib/rbac"

const ScriptGenerator = nextDynamic(() => import("./script-generator").then(m => m.ScriptGenerator))

export const dynamic = "force-dynamic"

export default async function ScriptsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const userProfile = await requireTab("Scripts", idToken)
  const client = api(session)

  let tabs: string[] = []
  let error: string | null = null

  try {
    tabs = await client.scripts.tabs()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load script tabs"
  }

  return (
    <ScriptGenerator
      tabs={tabs}
      tabsError={error}
      idToken={idToken}
      userRole={userProfile.role}
    />
  )
}
