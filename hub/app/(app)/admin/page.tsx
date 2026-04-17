import { auth } from "@/auth"
import { api, type UserProfile } from "@/lib/api"
import { requireAdmin } from "@/lib/rbac"
import { UsersPanel } from "./users-panel"

export const dynamic = "force-dynamic"

export default async function AdminPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const me = await requireAdmin(idToken)
  const client = api(session)

  let users: UserProfile[] = []
  let error: string | null = null

  try {
    users = await client.users.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load users"
  }

  return <UsersPanel users={users} error={error} idToken={idToken} currentEmail={me.email} />
}
