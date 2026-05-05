import { auth } from "@/auth"
import { api, type RevenueDashboard, type SceneRevenueRow, type CrossPlatformRevenueRow, type DailyRevenueSummary } from "@/lib/api"
import { requireAdmin } from "@/lib/rbac"
import { RevenueView } from "./revenue-view"

export const dynamic = "force-dynamic"

/**
 * Revenue console (admin-only).
 *
 * Surfaces the "Premium Breakdowns" Google Sheet — our consolidated
 * SLR/POVR/VRPorn earnings ledger — inside the hub. Server-fetches the
 * three pieces (dashboard + top scenes + cross-platform matches) in
 * parallel so the page renders in one round-trip.
 */
export default async function RevenuePage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireAdmin(idToken)
  const client = api(session)

  let dashboard: RevenueDashboard | null = null
  let topScenes: SceneRevenueRow[] = []
  let crossPlatform: CrossPlatformRevenueRow[] = []
  let daily: DailyRevenueSummary | null = null
  let error: string | null = null

  try {
    const [dRes, sRes, xRes, dayRes] = await Promise.allSettled([
      client.revenue.dashboard(),
      client.revenue.scenes({ order: "top", limit: 25 }),
      client.revenue.crossPlatform(25),
      client.revenue.daily(),
    ])
    if (dRes.status === "fulfilled") dashboard = dRes.value
    else error = dRes.reason instanceof Error ? dRes.reason.message : "Failed to load revenue dashboard"
    if (sRes.status === "fulfilled")   topScenes = sRes.value
    if (xRes.status === "fulfilled")   crossPlatform = xRes.value
    if (dayRes.status === "fulfilled") daily = dayRes.value
  } catch (e) {
    error = e instanceof Error ? e.message : "Revenue load failed"
  }

  return (
    <RevenueView
      dashboard={dashboard}
      topScenes={topScenes}
      crossPlatform={crossPlatform}
      daily={daily}
      error={error}
    />
  )
}
