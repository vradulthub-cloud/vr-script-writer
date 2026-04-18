import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Shoot } from "@/lib/api"
import { requireTab } from "@/lib/rbac"

const ShootBoard = nextDynamic(() => import("./shoot-board").then(m => m.ShootBoard))

export const dynamic = "force-dynamic"

export default async function ShootsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Shoots", idToken)
  const client = api(session)

  let shoots: Shoot[] = []
  let error: string | null = null

  try {
    // Default window: today-14 to today+14 (set server-side in router)
    shoots = await client.shoots.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load shoots"
  }

  return <ShootBoard initialShoots={shoots} error={error} idToken={idToken} />
}
