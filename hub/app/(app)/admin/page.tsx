import { auth } from "@/auth"
import { api, type UserProfile } from "@/lib/api"
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
    userProfile = await client.users.me()
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

  return (
    <div>
      <div className="mb-6">
        <h1>Admin</h1>
        <p data-subtitle>User management and permissions</p>
      </div>
      <UsersPanel users={users} error={error} idToken={idToken} />
    </div>
  )
}
