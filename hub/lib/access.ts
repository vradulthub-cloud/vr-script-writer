/**
 * Higher-tier access control.
 *
 * The standard admin gate is enforced through `requireAdmin` in lib/rbac.ts.
 * Some surfaces (currently the Revenue dashboard) need a stricter gate
 * because the data is sensitive financial information that even other
 * admins shouldn't see.
 *
 * Add an email here to grant Revenue access. The matching server-side gate
 * lives in api/auth.py's `require_revenue_viewer`. Both lists must agree —
 * granting one without the other either hides a real admin's link or shows
 * a link that 403s.
 */
export const REVENUE_VIEWER_EMAILS: ReadonlyArray<string> = [
  "andrewrowe72@gmail.com",
  "dev@eclatech.test",  // dev:mock harness — never exists in prod
] as const

export function canViewRevenue(email: string | undefined | null, role: string | undefined | null): boolean {
  if (!email) return false
  if ((role || "").toLowerCase() !== "admin") return false
  return REVENUE_VIEWER_EMAILS.includes(email.toLowerCase())
}
