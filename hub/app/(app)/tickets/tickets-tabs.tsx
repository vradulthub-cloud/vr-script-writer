"use client"

import { useState } from "react"
import { type Approval, type Ticket, type UserProfile } from "@/lib/api"
import { ApprovalList } from "../approvals/approval-list"
import { ApprovalSubmit } from "../approvals/approval-submit"
import { TicketList } from "./ticket-list"

interface Props {
  approvals: Approval[]
  approvalsError: string | null
  tickets: Ticket[]
  ticketsError: string | null
  users: UserProfile[]
  idToken: string | undefined
  userRole: string
}

const TABS = [
  { key: "approvals",  label: "Approvals" },
  { key: "open",       label: "Open Tickets" },
  { key: "in-review",  label: "In Review" },
  { key: "closed",     label: "Closed" },
  { key: "submit",     label: "Submit" },
] as const

type TabKey = (typeof TABS)[number]["key"]

export function TicketsTabs({
  approvals,
  approvalsError,
  tickets,
  ticketsError,
  users,
  idToken,
  userRole,
}: Props) {
  const [tab, setTab] = useState<TabKey>("approvals")

  const pendingCount  = approvals.filter(a => a.status === "Pending").length
  const openCount     = tickets.filter(t => t.status === "New" || t.status === "Approved" || t.status === "In Progress").length
  const reviewCount   = tickets.filter(t => t.status === "In Review").length
  const closedCount   = tickets.filter(t => t.status === "Closed" || t.status === "Rejected").length

  const counts: Record<TabKey, number | null> = {
    approvals:  pendingCount  || null,
    open:       openCount     || null,
    "in-review": reviewCount  || null,
    closed:     closedCount   || null,
    submit:     null,
  }

  return (
    <div>
      {/* Sub-tab bar */}
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
              {count ? (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    background: t.key === "approvals" ? "color-mix(in srgb, var(--color-warn) 18%, transparent)" : "var(--color-elevated)",
                    color: t.key === "approvals" ? "var(--color-warn)" : "var(--color-text-muted)",
                    border: t.key === "approvals" ? "1px solid color-mix(in srgb, var(--color-warn) 30%, transparent)" : "1px solid var(--color-border)",
                    borderRadius: 10,
                    padding: "1px 6px",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {count}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>

      {/* Tab panels */}
      {tab === "approvals" && (
        <ApprovalList
          initialApprovals={approvals}
          error={approvalsError}
          idToken={idToken}
        />
      )}

      {(tab === "open" || tab === "in-review" || tab === "closed") && (
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
      )}

      {tab === "submit" && (
        <ApprovalSubmit idToken={idToken} />
      )}
    </div>
  )
}
