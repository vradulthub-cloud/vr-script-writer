import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Model } from "@/lib/api"
import { requireTab } from "@/lib/rbac"

const ModelSearch = nextDynamic(() => import("./model-search").then(m => m.ModelSearch))

export const dynamic = "force-dynamic"

export default async function ResearchPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Model Research", idToken)
  const client = api(session)

  let models: Model[] = []
  let error: string | null = null

  try {
    models = await client.models.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load models"
  }

  return <ModelSearch models={models} error={error} idToken={idToken} />
}
