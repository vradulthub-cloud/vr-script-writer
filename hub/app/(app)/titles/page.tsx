import { TitleGenerator } from "./title-generator"
import { auth } from "@/auth"

export const dynamic = "force-dynamic"

export default async function TitlesPage() {
  const session = await auth()

  return (
    <div>
      <div className="page-header">
        <h1 className="tracking-tight">
          Title Card Generator
        </h1>
        <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
          Generate AI title card images for scenes
        </p>
      </div>
      <TitleGenerator idToken={(session as { idToken?: string } | null)?.idToken} />
    </div>
  )
}
