import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Shoot } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { ShootsV2View } from "./shoots-v2-view"

const ShootBoard = nextDynamic(() => import("./shoot-board").then(m => m.ShootBoard))

export const dynamic = "force-dynamic"

export default async function ShootsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Shoots", idToken)
  const client = api(session)
  const v2 = await isEclatechV2()

  let shoots: Shoot[] = []
  let error: string | null = null

  try {
    // Default window: today-14 to today+14 (set server-side in router)
    shoots = await client.shoots.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load shoots"
  }

  if (v2) {
    // v2: calendar overview on top; ShootBoard is the single shoot-row surface.
    return (
      <div>
        <style dangerouslySetInnerHTML={{ __html: `
          .ec-embed-board > div > .page-header,
          .ec-embed-board .page-header { display: none !important; }
        `}} />
        <ShootsV2View initialShoots={shoots} />
        <div className="ec-embed-board">
          <ShootBoard initialShoots={shoots} error={error} idToken={idToken} variant="v2" />
        </div>
      </div>
    )
  }

  return <ShootBoard initialShoots={shoots} error={error} idToken={idToken} />
}
