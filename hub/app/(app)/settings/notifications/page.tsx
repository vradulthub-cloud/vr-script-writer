import { auth } from "@/auth"
import { api, type NotificationPref } from "@/lib/api"
import { PrefsView } from "./prefs-view"

export const dynamic = "force-dynamic"

export default async function NotificationPrefsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const client = api(session)

  let prefs: NotificationPref[] = []
  let error: string | null = null
  try {
    prefs = await client.notifications.prefs()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load notification preferences"
  }

  return <PrefsView initial={prefs} initialError={error} idToken={idToken} />
}
