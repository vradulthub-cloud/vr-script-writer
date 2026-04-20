import { cookies } from "next/headers"

/** True when the Eclatech v2 redesign is enabled for this request.
 *  Checked via cookie (`/?eclatech=v2`) or build-time env flag.
 *  Server-only helper — safe to call from async server components/layouts. */
export async function isEclatechV2(): Promise<boolean> {
  const jar = await cookies()
  if (jar.get("eclatech")?.value === "v2") return true
  return process.env.NEXT_PUBLIC_ECLATECH_V2 === "1"
}
