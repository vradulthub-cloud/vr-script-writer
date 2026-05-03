import { cookies } from "next/headers"

/**
 * True when the Eclatech v2 redesign is enabled for this request.
 *
 * V2 is now the default. The flag stays so a per-request opt-out still
 * works during the transition window — visit `/?eclatech=v1` once and an
 * `eclatech=v1` cookie pins the old chrome for that browser. Visit
 * `/?eclatech=v2` to go back to V2, or clear the cookie.
 *
 * Server-only helper — safe to call from async server components/layouts.
 */
export async function isEclatechV2(): Promise<boolean> {
  const jar = await cookies()
  const val = jar.get("eclatech")?.value
  // Explicit opt-out via cookie wins over the default.
  if (val === "v1" || val === "off") return false
  // Env kill-switch — set to "0" to globally roll back if V2 regresses.
  if (process.env.NEXT_PUBLIC_ECLATECH_V2 === "0") return false
  return true
}
