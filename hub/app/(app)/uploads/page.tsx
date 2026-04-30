import { auth } from "@/auth"
import { api, type UploadHistoryRow } from "@/lib/api"
import { UploadsView } from "./uploads-view"

export const dynamic = "force-dynamic"

export default async function UploadsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken ?? ""
  const client = api(session)

  let history: UploadHistoryRow[] = []
  try {
    history = await client.uploads.history(50)
  } catch {
    // Non-fatal — page renders with empty history.
  }

  return <UploadsView idToken={idToken} initialHistory={history} />
}
