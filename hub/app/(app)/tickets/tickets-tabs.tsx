"use client"

import { useMemo, useState } from "react"
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
  v2?: boolean
}

const TABS_V1 = [
  { key: "approvals",  label: "Approvals" },
  { key: "open",       label: "Open Tickets" },
  { key: "in-review",  label: "In Review" },
  { key: "closed",     label: "Closed" },
  { key: "submit",     label: "Submit" },
] as const

const TABS_V2 = [
  { key: "approvals",  label: "Approvals" },
  { key: "open",       label: "Open Tickets" },
  { key: "in-review",  label: "In Review" },
  { key: "closed",     label: "Closed" },
] as const

type TabKeyV1 = (typeof TABS_V1)[number]["key"]
type TabKeyV2 = (typeof TABS_V2)[number]["key"]

export function TicketsTabs({
  approvals,
  approvalsError,
  tickets,
  ticketsError,
  users,
  idToken,
  userRole,
  v2 = false,
}: Props) {
  return v2 ? (
    <V2Layout
      approvals={approvals}
      approvalsError={approvalsError}
      tickets={tickets}
      ticketsError={ticketsError}
      users={users}
      idToken={idToken}
      userRole={userRole}
    />
  ) : (
    <V1Layout
      approvals={approvals}
      approvalsError={approvalsError}
      tickets={tickets}
      ticketsError={ticketsError}
      users={users}
      idToken={idToken}
      userRole={userRole}
    />
  )
}

/* ─── v1 (existing) ────────────────────────────────────────────────────────── */
function V1Layout({
  approvals,
  approvalsError,
  tickets,
  ticketsError,
  users,
  idToken,
  userRole,
}: Omit<Props, "v2">) {
  const [tab, setTab] = useState<TabKeyV1>("approvals")

  const pendingCount  = approvals.filter(a => a.status === "Pending").length
  const openCount     = tickets.filter(t => t.status === "New" || t.status === "Approved" || t.status === "In Progress").length
  const reviewCount   = tickets.filter(t => t.status === "In Review").length
  const closedCount   = tickets.filter(t => t.status === "Closed" || t.status === "Rejected").length

  const counts: Record<TabKeyV1, number | null> = {
    approvals:  pendingCount  || null,
    open:       openCount     || null,
    "in-review": reviewCount  || null,
    closed:     closedCount   || null,
    submit:     null,
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid var(--color-border)",
          marginBottom: 20,
        }}
      >
        {TABS_V1.map(t => {
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

/* ─── v2 (prototype-inspired) ──────────────────────────────────────────────── */
function V2Layout({
  approvals,
  approvalsError,
  tickets,
  ticketsError,
  users,
  idToken,
  userRole,
}: Omit<Props, "v2">) {
  const [tab, setTab] = useState<TabKeyV2>("approvals")

  const pendingCount = approvals.filter(a => a.status === "Pending").length
  const openCount    = tickets.filter(t => t.status === "New" || t.status === "Approved" || t.status === "In Progress").length
  const reviewCount  = tickets.filter(t => t.status === "In Review").length
  const closedCount  = tickets.filter(t => t.status === "Closed" || t.status === "Rejected").length

  const counts: Record<TabKeyV2, number> = {
    approvals: pendingCount,
    open: openCount,
    "in-review": reviewCount,
    closed: closedCount,
  }

  return (
    <div className="ec-cols">
      <div className="ec-col">
        <div className="ec-seg" role="tablist" aria-label="Tickets">
          {TABS_V2.map(t => (
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
      </div>

      <div className="ec-col">
        <QueueHealth approvals={approvals} tickets={tickets} />
        <div className="ec-block">
          <header><h2>Submit Ticket</h2></header>
          <div style={{ padding: 14 }}>
            <ApprovalSubmit idToken={idToken} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── Queue Health panel (derived from local arrays; TODO: real API) ───────── */
function QueueHealth({ approvals, tickets }: { approvals: Approval[]; tickets: Ticket[] }) {
  const stats = useMemo(() => {
    const now = Date.now()
    const WEEK = 7 * 24 * 60 * 60 * 1000

    const last7 = approvals.filter(a => {
      const t = Date.parse(a.submitted_at || "")
      return Number.isFinite(t) && now - t < WEEK
    })

    // Avg time-to-decision for decided approvals in the last 30 days
    const decided = approvals.filter(a => {
      const sub = Date.parse(a.submitted_at || "")
      const dec = Date.parse(a.decided_at || "")
      return Number.isFinite(sub) && Number.isFinite(dec) && dec >= sub
    })
    const avgMs = decided.length
      ? decided.reduce((s, a) => s + (Date.parse(a.decided_at) - Date.parse(a.submitted_at)), 0) / decided.length
      : 0

    // Approval rate over all decided items in the last 7 days
    const decided7 = decided.filter(a => now - Date.parse(a.decided_at) < WEEK)
    const approved7 = decided7.filter(a => a.status === "Approved").length
    const rate = decided7.length ? Math.round((approved7 / decided7.length) * 100) : null

    return {
      avgResponse: formatDuration(avgMs),
      approvalRate: rate,
      weekCount: last7.length,
    }
  }, [approvals, tickets])

  return (
    <div className="ec-block ec-inverted">
      <header><h2>Queue Health</h2></header>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        <HealthStat
          label="Avg Response"
          value={stats.avgResponse ?? "—"}
          hint={stats.avgResponse ? undefined : "no decisions yet"}
        />
        <HealthStat
          label="Approval Rate · 7d"
          value={stats.approvalRate == null ? "—" : `${stats.approvalRate}%`}
          hint={stats.approvalRate == null ? "no decisions this week" : undefined}
        />
        <HealthStat label="Submissions · Week" value={String(stats.weekCount)} />
      </div>
    </div>
  )
}

function HealthStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const isEmpty = value === "—"
  return (
    <div>
      <div
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.45)",
        }}
      >
        {label}
      </div>
      <div
        style={{
          marginTop: 4,
          fontWeight: 800,
          fontSize: isEmpty ? 28 : 36,
          letterSpacing: "-0.03em",
          fontFamily: "var(--font-display-hero)",
          color: isEmpty ? "rgba(255,255,255,0.45)" : undefined,
        }}
      >
        {value}
      </div>
      {hint && (
        <div
          style={{
            marginTop: 4,
            fontSize: 10,
            color: "rgba(255,255,255,0.35)",
            letterSpacing: "0.02em",
          }}
        >
          {hint}
        </div>
      )}
    </div>
  )
}

function formatDuration(ms: number): string | null {
  if (!ms || !Number.isFinite(ms)) return null
  const hours = Math.floor(ms / 3600000)
  const mins = Math.floor((ms % 3600000) / 60000)
  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    return `${days}d ${hours % 24}h`
  }
  return `${hours}h ${String(mins).padStart(2, "0")}m`
}
