import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Model } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { ResearchV2View } from "./research-v2-view"

const ModelSearch = nextDynamic(() => import("./model-search").then(m => m.ModelSearch))

export const dynamic = "force-dynamic"

export default async function ResearchPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Model Research", idToken)
  const client = api(session)
  const v2 = await isEclatechV2()

  let models: Model[] = []
  let error: string | null = null

  try {
    models = await client.models.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load models"
  }

  if (v2) {
    return (
      <div>
        <ResearchV2View models={models} />
        <div className="ec-embed-grid">
          <ModelSearch models={models} error={error} idToken={idToken} />
        </div>
      </div>
    )
  }

  return <ModelSearch models={models} error={error} idToken={idToken} />
}
