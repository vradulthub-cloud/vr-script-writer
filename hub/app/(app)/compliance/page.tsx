import { auth } from "@/auth"
import { api, type ComplianceShoot } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { ComplianceView } from "./compliance-view"

export const dynamic = "force-dynamic"

export default async function CompliancePage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Shoots", idToken)
  const client = api(session)

  const today = new Date().toISOString().slice(0, 10)
  let shoots: ComplianceShoot[] = []
  let error: string | null = null

  try {
    shoots = await client.compliance.shoots(today)
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load shoots"
  }

  return (
    <ComplianceView
      initialShoots={shoots}
      initialDate={today}
      idToken={idToken}
      loadError={error}
    />
  )
}
