import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { api, type UserProfile } from "@/lib/api"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { MobileNav } from "./mobile-nav"
import { CommandPalette } from "@/components/ui/command-palette"
import { Toaster } from "@/components/ui/toast"

export async function AppShell({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect("/login")

  // Fetch current user profile (role + allowed_tabs) from API
  let userProfile: UserProfile | null = null
  try {
    userProfile = await api(session).users.me()
  } catch (err) {
    // /api/me failed — allow through with no tab restrictions, but log so the
    // error is findable in server logs
    console.error("[hub] /api/users/me failed in AppShell:", err)
  }

  const idToken = (session as { idToken?: string } | null)?.idToken

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
