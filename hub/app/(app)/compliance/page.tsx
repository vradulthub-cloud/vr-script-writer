import { auth } from "@/auth"
import { api, type ComplianceShoot } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { ComplianceView } from "./compliance-view"

export const dynamic = "force-dynamic"

export default async function CompliancePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>
}) {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Shoots", idToken)
  const client = api(session)

  const sp = await searchParams
  // Use America/New_York so "today" is correct for production shoots regardless
  // of the Vercel edge node's UTC offset.
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date())
  const initialDate = sp.date ?? today
  let shoots: ComplianceShoot[] = []
  let error: string | null = null

  try {
    shoots = await client.compliance.shoots(initialDate)
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load shoots"
  }

  return (
    <ComplianceView
      initialShoots={shoots}
      initialDate={initialDate}
      idToken={idToken}
      loadError={error}
    />
  )
}
