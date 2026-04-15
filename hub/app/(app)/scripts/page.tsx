import { auth } from "@/auth"
import { api } from "@/lib/api"
import { ScriptGenerator } from "./script-generator"

export const dynamic = "force-dynamic"

export default async function ScriptsPage() {
  const session = await auth()
  const client = api(session)

  let tabs: string[] = []
  let error: string | null = null

  try {
    tabs = await client.scripts.tabs()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load script tabs"
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="font-semibold tracking-tight" style={{ fontSize: 16, color: "var(--color-text)" }}>
          Script Generator
        </h1>
        <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
          Generate AI scripts manually or from a shoot sheet row
        </p>
      </div>
      <ScriptGenerator
        tabs={tabs}
        tabsError={error}
        idToken={(session as { idToken?: string } | null)?.idToken}
      />
    </div>
  )
}
