import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"

export async function AppShell({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect("/login")

  return (
    <div className="min-h-screen" style={{ background: "var(--color-base)" }}>
      <Sidebar />
      <Topbar session={session} />
      <main
        className="overflow-y-auto"
        style={{
          marginLeft: "var(--spacing-sidebar)",
          paddingTop: "var(--spacing-topbar)",
          minHeight: "100vh",
        }}
      >
        <div className="p-6">{children}</div>
      </main>
    </div>
  )
}
