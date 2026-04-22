"use client"

import { useState } from "react"
import { type Ticket, type UserProfile } from "@/lib/api"
import { TicketList } from "./ticket-list"

/**
 * Approvals + Submit tabs were removed from /tickets per product call —
 * the team isn't using approvals yet, so a tab leading to an empty
 * surface (and a Submit form whose target is unused) just adds chrome.
 *
 * Approvals is still reachable at its own /approvals route for
 * notification deep-links and a future re-introduction. The two tabs
 * here can be added back by reverting this file plus the page.tsx
 * data fetch.
 */

interface Props {
  tickets: Ticket[]
  ticketsError: string | null
  users: UserProfile[]
  idToken: string | undefined
  userRole: string
  v2?: boolean
}

const TABS = [
  { key: "open",      label: "Open Tickets" },
  { key: "in-review", label: "In Review" },
  { key: "closed",    label: "Closed" },
] as const

type TabKey = (typeof TABS)[number]["key"]

export function TicketsTabs({
  tickets,
  ticketsError,
  users,
  idToken,
  userRole,
  v2 = false,
}: Props) {
  const [tab, setTab] = useState<TabKey>("open")

  const openCount   = tickets.filter(t => t.status === "New" || t.status === "Approved" || t.status === "In Progress").length
  const reviewCount = tickets.filter(t => t.status === "In Review").length
  const closedCount = tickets.filter(t => t.status === "Closed" || t.status === "Rejected").length

  const counts: Record<TabKey, number> = {
    open: openCount,
    "in-review": reviewCount,
    closed: closedCount,
  }

  // V2 keeps the segmented-control look-and-feel from the redesign;
  // V1 keeps the original underline-tab look. Same content either way.
  return v2 ? (
    <div>
      <div className="ec-seg" role="tablist" aria-label="Tickets" style={{ marginBottom: 18 }}>
        {TABS.map(t => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
          >
            {t.label}
            {counts[t.key] ? <span className="c">{counts[t.key]}</span> : null}
          </button>
        ))}
      </div>
      <TicketList
        tickets={tickets}
        users={users}
        error={ticketsError}
        idToken={idToken}
        userRole={userRole}
        defaultStatusFilter={
          tab === "open"      ? "open"      :
          tab === "in-review" ? "In Review" :
          "closed"
        }
      />
    </div>
  ) : (
    <div>
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid var(--color-border)",
          marginBottom: 20,
        }}
      >
        {TABS.map(t => {
          const active = tab === t.key
          const count = counts[t.key]
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                padding: "9px 14px",
                fontSize: 11,
                fontWeight: active ? 600 : 400,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: active ? "var(--color-text)" : "var(--color-text-muted)",
                background: "none",
                border: "none",
                borderBottom: active ? "2px solid var(--color-lime)" : "2px solid transparent",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: -1,
                transition: "color 120ms, border-color 120ms",
              }}
            >
              {t.label}
              {count > 0 && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    background: "var(--color-elevated)",
                    color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 10,
                    padding: "1px 6px",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>
      <TicketList
        tickets={tickets}
        users={users}
        error={ticketsError}
        idToken={idToken}
        userRole={userRole}
        defaultStatusFilter={
          tab === "open"      ? "open"      :
          tab === "in-review" ? "In Review" :
          "closed"
        }
      />
    </div>
  )
}
