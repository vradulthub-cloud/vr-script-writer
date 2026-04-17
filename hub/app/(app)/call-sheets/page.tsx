import { auth } from "@/auth"
import { requireTab } from "@/lib/rbac"
import { CallSheetsClient } from "./call-sheets-client"

export const dynamic = "force-dynamic"

export default async function CallSheetsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Call Sheets", idToken)

  return <CallSheetsClient />
}
