"use client"

import { useEffect, useState, useMemo } from "react"
import { api, type Ticket } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { Panel } from "@/components/ui/panel"

/** Audit log of permission changes.
 *
 *  Background: every save in the User Permissions table writes a
 *  synthetic ticket with `type=Audit` (see users-panel.tsx). The Tickets
 *  sheet is the closest thing we have to an append-only audit trail —
 *  there's no dedicated audit table, and the users sheet has no history.
 *  This panel filters those out so admins can scroll back through "who
 *  promoted whom, when" without polluting the regular Tickets view.
 */
export function AuditLogPanel({ idToken: serverIdToken }: { idToken?: string }) {
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [rows, setRows] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    client.tickets.list({ type: "Audit", limit: 25 })
      .then(list => { if (alive) { setRows(list); setErr(null) } })
      .catch(e => { if (alive) setErr(e instanceof Error ? e.message : "Failed to load audit log") })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [client])

  return (
    <Panel>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--color-text)" }}>
            Audit Log
          </h2>
          <span style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
            Permission changes · last 25
          </span>
        </div>
        {loading && <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>Loading…</div>}
        {err && <div style={{ fontSize: 12, color: "var(--color-err)" }}>{err}</div>}
        {!loading && !err && rows.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>No permission changes recorded yet.</div>
        )}
        {!loading && !err && rows.length > 0 && (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 6 }}>
            {rows.map(t => {
              // Title format from users-panel.tsx is:
              //   "Admin change: <email> — <change list>"
              // Pull the email + change apart so we can render them with
              // distinct weight, like a real diff line.
              const parsed = parseAuditTitle(t.title)
              return (
                <li
                  key={t.ticket_id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "120px 1fr auto",
                    gap: 12,
                    padding: "8px 10px",
                    border: "1px solid var(--color-border-subtle)",
                    borderRadius: 4,
                    background: "var(--color-elevated)",
                    alignItems: "baseline",
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontVariantNumeric: "tabular-nums",
                      color: "var(--color-text-faint)",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatTimestamp(t.submitted_at)}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.4 }}>
                    {parsed.email && (
                      <span style={{ fontWeight: 600 }}>{parsed.email}</span>
                    )}
                    {parsed.change && (
                      <>
                        {parsed.email ? " — " : ""}
                        <span style={{ color: "var(--color-text-muted)" }}>{parsed.change}</span>
                      </>
                    )}
                    {!parsed.email && !parsed.change && t.title}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      color: "var(--color-text-faint)",
                      letterSpacing: "0.04em",
                      whiteSpace: "nowrap",
                    }}
                    title={`Submitted by ${t.submitted_by}`}
                  >
                    by {t.submitted_by || "—"}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Panel>
  )
}

function parseAuditTitle(title: string): { email: string; change: string } {
  // "Admin change: alex@eclatech.test — role editor → admin"
  const stripped = title.replace(/^Admin change:\s*/, "")
  const dashIdx = stripped.indexOf("—")
  if (dashIdx < 0) return { email: stripped.trim(), change: "" }
  return {
    email: stripped.slice(0, dashIdx).trim(),
    change: stripped.slice(dashIdx + 1).trim(),
  }
}

function formatTimestamp(iso: string): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  // Compact "Apr 21 15:30" — saves horizontal room since the year is
  // almost always implied by the page context.
  const month = d.toLocaleString("en-US", { month: "short" })
  const day = String(d.getDate()).padStart(2, "0")
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${month} ${day} ${hh}:${mm}`
}
