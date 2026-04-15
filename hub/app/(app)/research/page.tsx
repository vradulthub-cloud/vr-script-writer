import { auth } from "@/auth"
import { api, type Model } from "@/lib/api"
import { ModelSearch } from "./model-search"

export const dynamic = "force-dynamic"

export default async function ResearchPage() {
  const session = await auth()
  const client = api(session)

  let models: Model[] = []
  let error: string | null = null

  try {
    models = await client.models.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load models"
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="font-semibold tracking-tight" style={{ fontSize: 16, color: "var(--color-text)" }}>
          Model Research
        </h1>
        <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
          Agency info, rates, and notes for talent
        </p>
      </div>
      <ModelSearch models={models} error={error} />
    </div>
  )
}
