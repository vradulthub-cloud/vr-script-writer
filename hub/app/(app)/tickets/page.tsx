import { auth } from "@/auth"
import { api, type Ticket, type TicketStats } from "@/lib/api"
import { TicketList } from "./ticket-list"

export const dynamic = "force-dynamic"

export default async function TicketsPage() {
  const session = await auth()
  const client = api(session)

  let tickets: Ticket[] = []
  let stats: TicketStats = {}
  let error: string | null = null

  try {
    ;[tickets, stats] = await Promise.all([client.tickets.list(), client.tickets.stats()])
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load tickets"
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1
            className="font-semibold tracking-tight"
            style={{ fontSize: 16, color: "var(--color-text)" }}
          >
            Tickets
          </h1>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
            Bug reports, feature requests, and tasks
          </p>
        </div>
      </div>

      {/* Stats row */}
      {!error && (
        <div className="flex gap-3 mb-6 flex-wrap">
          {STAT_CONFIGS.map(({ key, label, color }) => (
            <div
              key={key}
              className="rounded px-3 py-2"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                minWidth: 80,
              }}
            >
              <p
                className="font-semibold tabular-nums"
                style={{ fontSize: 20, color }}
              >
                {stats[key] ?? 0}
              </p>
              <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 1 }}>
                {label}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Ticket list (client component for interactivity) */}
      <TicketList tickets={tickets} error={error} idToken={(session as { idToken?: string } | null)?.idToken} />
    </div>
  )
}

const STAT_CONFIGS = [
  { key: "New",         label: "New",         color: "var(--color-text)" },
  { key: "Approved",    label: "Approved",    color: "var(--color-ok)" },
  { key: "In Progress", label: "In Progress", color: "#60a5fa" },
  { key: "In Review",   label: "In Review",   color: "var(--color-lime)" },
  { key: "Closed",      label: "Closed",      color: "var(--color-text-faint)" },
] as const
