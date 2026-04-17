import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { cachedUsersMe, type UserProfile } from "@/lib/api"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { MobileNav } from "./mobile-nav"
import { CommandPalette } from "@/components/ui/command-palette"
import { Toaster } from "@/components/ui/toast"

export async function AppShell({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect("/login")

  const idToken = (session as { idToken?: string } | null)?.idToken

  // cachedUsersMe dedupes within the same render tree, so pages that also
  // fetch users.me() (dashboard, descriptions, scripts, admin) share this
  // single request instead of firing a duplicate.
  let userProfile: UserProfile | null = null
  try {
    userProfile = await cachedUsersMe(idToken)
  } catch (err) {
    console.error("[hub] /api/users/me failed in AppShell:", err)
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--color-base)" }}>
      <Sidebar
        allowedTabs={userProfile?.allowed_tabs ?? "ALL"}
        userRole={userProfile?.role ?? "editor"}
      />
      <Topbar session={session} idToken={idToken} userRole={userProfile?.role ?? "editor"} />
      <main
        className="overflow-y-auto"
        style={{
          marginLeft: "var(--spacing-sidebar)",
          paddingTop: "var(--spacing-topbar)",
          minHeight: "100vh",
        }}
      >
        <div style={{ padding: "28px 32px 40px" }}>{children}</div>
      </main>
      <MobileNav />
      <CommandPalette />
      <Toaster />
    </div>
  )
}
