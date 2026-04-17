import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { requireProfile } from "@/lib/rbac"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { MobileNav } from "./mobile-nav"
import { CommandPalette } from "@/components/ui/command-palette"
import { Toaster } from "@/components/ui/toast"

export async function AppShell({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect("/login")

  const idToken = (session as { idToken?: string } | null)?.idToken

  // Fail closed: if the profile fetch fails, requireProfile redirects to
  // /login?error=no-profile rather than defaulting to ALL / editor, which
  // would grant every signed-in Google user full access on any backend
  // hiccup. cachedUsersMe dedupes within the render tree, so pages that
  // also call it share this single request.
  const userProfile = await requireProfile(idToken)

  return (
    <div className="min-h-screen" style={{ background: "var(--color-base)" }}>
      <Sidebar
        allowedTabs={userProfile.allowed_tabs}
        userRole={userProfile.role}
      />
      <Topbar session={session} idToken={idToken} userRole={userProfile.role} />
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
