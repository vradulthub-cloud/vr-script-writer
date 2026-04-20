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
    // Hybrid: calendar + roster overview at top, full asset-edit grid below.
    return (
      <div>
        <style dangerouslySetInnerHTML={{ __html: `
          .ec-embed-board > div > .page-header,
          .ec-embed-board .page-header { display: none !important; }
          .ec-embed-board::before {
            content: "Asset grid";
            display: block;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--color-text-muted);
            padding-bottom: 10px;
            margin-bottom: 14px;
            border-bottom: 1px solid var(--color-border);
          }
        `}} />
        <ShootsV2View initialShoots={shoots} />
        <div className="ec-embed-board" style={{ marginTop: 32 }}>
          <ShootBoard initialShoots={shoots} error={error} idToken={idToken} />
        </div>
      </div>
    )
  }

  return <ShootBoard initialShoots={shoots} error={error} idToken={idToken} />
}
