import { auth } from "@/auth"
import { api, type Scene, type UserProfile } from "@/lib/api"
import { DescGenerator } from "./desc-generator"

export const dynamic = "force-dynamic"

export default async function DescriptionsPage() {
  const session = await auth()
  const client = api(session)

  let scenes: Scene[] = []
  let error: string | null = null
  let userProfile: UserProfile | null = null

  try {
    scenes = await client.scenes.list({ limit: 500 })
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load scenes"
  }

  try {
    userProfile = await client.users.me()
  } catch {}

  return (
    <div>
      <div className="mb-6">
        <h1 className="tracking-tight">
          Description Generator
        </h1>
        <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
          Generate SEO-optimised scene descriptions
        </p>
      </div>
      <DescGenerator
        scenes={scenes}
        scenesError={error}
        idToken={(session as { idToken?: string } | null)?.idToken}
        userRole={userProfile?.role}
      />
    </div>
  )
}
