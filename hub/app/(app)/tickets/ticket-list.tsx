"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import type { Ticket } from "@/lib/api"

const PRIORITY_COLOR: Record<string, string> = {
  Critical: "var(--color-err)",
  High:     "#f97316",
  Medium:   "var(--color-warn)",
  Low:      "var(--color-text-muted)",
}

const STATUS_COLOR: Record<string, string> = {
  "New":         "var(--color-text-muted)",
  "Approved":    "var(--color-ok)",
  "In Progress": "#60a5fa",
  "In Review":   "var(--color-lime)",
  "Closed":      "var(--color-text-faint)",
  "Rejected":    "var(--color-err)",
}

const STATUSES = ["All", "New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]

interface Props {
  tickets: Ticket[]
  error: string | null
}

export function TicketList({ tickets, error }: Props) {
  const [statusFilter, setStatusFilter] = useState("All")

  const filtered =
    statusFilter === "All"
      ? tickets
      : tickets.filter((t) => t.status === statusFilter)

  return (
    <div>
      {/* Filter bar */}
      <div className="flex gap-1 mb-4 flex-wrap">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className="px-2.5 py-1 rounded text-xs transition-colors"
            style={{
              background:
                statusFilter === s ? "var(--color-elevated)" : "transparent",
              color:
                statusFilter === s
                  ? "var(--color-text)"
                  : "var(--color-text-muted)",
              border: `1px solid ${
                statusFilter === s ? "var(--color-border)" : "transparent"
              }`,
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Error state */}
      {error && (
        <div
          className="rounded p-4 text-sm"
          style={{
            background: "color-mix(in srgb, var(--color-err) 10%, var(--color-surface))",
            border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
            color: "var(--color-err)",
          }}
        >
          {error}
          <p className="mt-1 text-xs opacity-70">
            Make sure the FastAPI backend is running on port 8502.
          </p>
        </div>
      )}

      {/* Empty state */}
      {!error && filtered.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
          No tickets{statusFilter !== "All" ? ` with status "${statusFilter}"` : ""}.
        </p>
      )}

      {/* Table */}
      {!error && filtered.length > 0 && (
        <div
          className="rounded overflow-hidden"
          style={{ border: "1px solid var(--color-border)" }}
        >
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                {["ID", "Title", "Project", "Priority", "Status", "By", "Date"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2 font-medium"
                    style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((ticket, i) => (
                <tr
                  key={ticket.ticket_id}
                  className="transition-colors hover:bg-[--color-elevated] cursor-pointer"
                  style={{
                    borderBottom:
                      i < filtered.length - 1
                        ? "1px solid var(--color-border-subtle)"
                        : undefined,
                  }}
                >
                  <td className="px-3 py-2.5 font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                    {ticket.ticket_id}
                  </td>
                  <td className="px-3 py-2.5" style={{ fontSize: 12, maxWidth: 320 }}>
                    <span className="line-clamp-1">{ticket.title}</span>
                    {ticket.description && (
                      <span
                        className="block line-clamp-1 mt-0.5"
                        style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                      >
                        {ticket.description}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                    {ticket.project || "—"}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <Badge
                      label={ticket.priority}
                      color={PRIORITY_COLOR[ticket.priority] ?? "var(--color-text-muted)"}
                    />
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <Badge
                      label={ticket.status}
                      color={STATUS_COLOR[ticket.status] ?? "var(--color-text-muted)"}
                    />
                  </td>
                  <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                    {ticket.submitted_by || "—"}
                  </td>
                  <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                    {ticket.submitted_at ? ticket.submitted_at.slice(0, 10) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-sm"
      style={{
        fontSize: 10,
        fontWeight: 500,
        letterSpacing: "0.02em",
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      {label}
    </span>
  )
}
