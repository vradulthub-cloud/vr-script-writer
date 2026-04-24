import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { requireProfile } from "@/lib/rbac"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { MobileNav } from "./mobile-nav"
import { CommandPalette } from "@/components/ui/command-palette"
import { Toaster } from "@/components/ui/toast"

const MOCK_PROFILE = { email: "dev@eclatech.test", name: "Dev Admin", role: "admin", allowed_tabs: "ALL" }
const MOCK_SESSION = { user: { name: "Dev Admin", email: "dev@eclatech.test", image: null }, idToken: "DEV_MOCK_TOKEN", expires: "" }

export async function AppShell({ children }: { children: React.ReactNode }) {
  const skipAuth = process.env.SKIP_AUTH === "1"

  const session = skipAuth ? MOCK_SESSION : await auth()
  if (!session) redirect("/login")

  const idToken = (session as { idToken?: string } | null)?.idToken
  const userProfile = skipAuth ? MOCK_PROFILE : await requireProfile(idToken)

  return (
    <div className="min-h-screen" style={{ background: "var(--color-base)" }}>
      <Sidebar
        allowedTabs={userProfile.allowed_tabs}
        userRole={userProfile.role}
      />
      <Topbar session={session} idToken={idToken} userRole={userProfile.role} disablePolling={skipAuth} />
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
