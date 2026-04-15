import { auth } from "@/auth"
import { api, type Ticket, type TicketStats, type UserProfile } from "@/lib/api"
import { TicketList } from "./ticket-list"
import { TicketsPageShell } from "./tickets-page-shell"
import { UsersPanel } from "./users-panel"

export const dynamic = "force-dynamic"

export default async function TicketsPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

  let tickets: Ticket[] = []
  let stats: TicketStats = {}
  let error: string | null = null
  let userProfile: UserProfile | null = null
  let allUsers: UserProfile[] = []
  let usersError: string | null = null

  try {
    ;[tickets, stats] = await Promise.all([client.tickets.list(), client.tickets.stats()])
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load tickets"
  }

  // Fetch user profile to check if admin
  try {
    userProfile = await client.users.me()
  } catch {
    // Non-critical — just won't show Users tab
  }

  const isAdmin = userProfile?.role === "admin"

  // Fetch users list for admins
  if (isAdmin) {
    try {
      allUsers = await client.users.list()
    } catch (e) {
      usersError = e instanceof Error ? e.message : "Failed to load users"
    }
  }

  return (
    <TicketsPageShell isAdmin={isAdmin}>
      {{
        tickets: (
          <div>
            {/* Stats row */}
            {!error && (
              <div className="flex gap-3 mb-6 flex-wrap">
                {STAT_CONFIGS.map(({ key, label, color }) => {
                  const count = stats[key] ?? 0
                  return (
                    <div
                      key={key}
                      className="rounded-lg px-4 py-3"
                      style={{
                        background: count > 0
                          ? `color-mix(in srgb, ${color} 6%, var(--color-surface))`
                          : "var(--color-surface)",
                        border: `1px solid ${count > 0
                          ? `color-mix(in srgb, ${color} 20%, transparent)`
                          : "var(--color-border)"}`,
                        minWidth: 90,
                      }}
                    >
                      <p
                        className="font-bold tabular-nums"
                        style={{ fontSize: 28, color, lineHeight: 1, letterSpacing: "-0.02em" }}
                      >
                        {count}
                      </p>
                      <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4, fontWeight: 500, letterSpacing: "0.02em" }}>
                        {label}
                      </p>
                    </div>
                  )
                })}
              </div>
            )}

            <TicketList tickets={tickets} error={error} idToken={idToken} />
          </div>
        ),
        users: isAdmin ? (
          <UsersPanel users={allUsers} error={usersError} idToken={idToken} />
        ) : null,
      }}
    </TicketsPageShell>
  )
}

const STAT_CONFIGS = [
  { key: "New",         label: "New",         color: "var(--color-text)" },
  { key: "Approved",    label: "Approved",    color: "var(--color-ok)" },
  { key: "In Progress", label: "In Progress", color: "#60a5fa" },
  { key: "In Review",   label: "In Review",   color: "var(--color-lime)" },
  { key: "Closed",      label: "Closed",      color: "var(--color-text-faint)" },
] as const
