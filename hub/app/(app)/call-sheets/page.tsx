import { auth } from "@/auth"
import { api } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { CallSheetsClient } from "./call-sheets-client"

export const dynamic = "force-dynamic"

export default async function CallSheetsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Call Sheets", idToken)
  const client = api(session)

  let tabs: string[] = []
  let tabsError: string | null = null
  try {
    tabs = await client.callSheets.tabs()
  } catch (e) {
    tabsError = e instanceof Error ? e.message : "Failed to load budget tabs"
  }

  return <CallSheetsClient idToken={idToken} initialTabs={tabs} initialTabsError={tabsError} />
}
