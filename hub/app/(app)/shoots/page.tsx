import { auth } from "@/auth"
import { api, type Shoot } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { ShootsV2View } from "./shoots-v2-view"

export const dynamic = "force-dynamic"

export default async function ShootsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Shoots", idToken)
  const client = api(session)

  let shoots: Shoot[] = []
  let error: string | null = null

  try {
    shoots = await client.shoots.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load shoots"
  }

  return (
    <ShootsV2View initialShoots={shoots} idToken={idToken} boardError={error} />
  )
}
