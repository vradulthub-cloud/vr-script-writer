import { auth } from "@/auth"
import { api, cachedUsersMe, type UserProfile } from "@/lib/api"
import { redirect } from "next/navigation"
import { UsersPanel } from "./users-panel"

export const dynamic = "force-dynamic"

export default async function AdminPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

  // Verify admin access
  let userProfile: UserProfile | null = null
  try {
    userProfile = await cachedUsersMe(idToken)
  } catch {
    redirect("/missing")
  }

  if (userProfile?.role !== "admin") {
    redirect("/missing")
  }

  let users: UserProfile[] = []
  let error: string | null = null

  try {
    users = await client.users.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load users"
  }

  return <UsersPanel users={users} error={error} idToken={idToken} />
}
