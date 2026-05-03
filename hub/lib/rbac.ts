/**
 * Server-side RBAC guards for route-level authorization.
 *
 * The sidebar filters nav items by users.allowed_tabs, but the sidebar is
 * only a UI hint — an authenticated user who knows a URL can still hit
 * /tickets, /scripts, etc. directly. These helpers ensure every page runs
 * the same check the sidebar does, and also fail closed if the user
 * profile can't be fetched (otherwise a backend hiccup silently grants
 * full access).
 */

import { redirect } from "next/navigation"
import { cachedUsersMe, type UserProfile } from "./api"

const SKIP_AUTH = process.env.SKIP_AUTH === "1"
const MOCK_PROFILE: UserProfile = {
  email: "dev@eclatech.test",
  name: "Dev Admin",
  role: "admin",
  allowed_tabs: "ALL",
}

/**
 * Load the current user's profile or redirect to /login.
 *
 * Use this at the top of any server component that needs a profile.
 * Unlike inline try/catch + `?? defaults`, this never returns a
 * permissive fallback — if the backend fails, the user sees login,
 * not full access.
 */
export async function requireProfile(idToken: string | undefined): Promise<UserProfile> {
  if (SKIP_AUTH) return MOCK_PROFILE
  if (!idToken) redirect("/login")
  let profile: UserProfile | null = null
  try {
    profile = await cachedUsersMe(idToken)
  } catch {
    // Swallow — we fail closed below.
  }
  if (!profile) redirect("/login?error=no-profile")
  return profile
}

/**
 * Require that the current user's allowed_tabs includes `tabKey`.
 *
 * Admins always pass. "ALL" always passes. Anything else is checked
 * against the comma-separated list. On denial, redirects to the
 * dashboard with ?error=no-access.
 */
export async function requireTab(
  tabKey: string,
  idToken: string | undefined,
): Promise<UserProfile> {
  const profile = await requireProfile(idToken)
  if ((profile.role ?? "").toLowerCase() === "admin") return profile
  const allowed = profile.allowed_tabs ?? ""
  if (allowed === "ALL") return profile
  const tabs = new Set(
    allowed.split(",").map((t) => t.trim()).filter(Boolean),
  )
  if (!tabs.has(tabKey)) redirect("/dashboard?error=no-access")
  return profile
}

/**
 * Require that the current user is an admin. On denial, redirects to
 * the dashboard with ?error=no-access.
 */
export async function requireAdmin(idToken: string | undefined): Promise<UserProfile> {
  const profile = await requireProfile(idToken)
  if ((profile.role ?? "").toLowerCase() !== "admin") redirect("/dashboard?error=no-access")
  return profile
}
