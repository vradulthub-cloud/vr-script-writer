import { auth } from "@/auth"
import { api, type TicketStats } from "@/lib/api"
import { studioColor, studioAbbr } from "@/lib/studio-colors"
import Link from "next/link"
import {
  LayoutGrid,
  Users,
  FileText,
  Phone,
  Image,
  AlignLeft,
  Layers,
  Ticket,
  CheckSquare,
  ArrowUpRight,
} from "lucide-react"
import { NotificationFeed } from "./notification-feed"

export const dynamic = "force-dynamic"

const ALL_MODULES = [
  { href: "/missing",      label: "Missing Assets",  icon: LayoutGrid,  tabKey: "Tickets",        hint: "Asset gaps" },
  { href: "/research",     label: "Model Research",  icon: Users,        tabKey: "Model Research", hint: "Performer profiles" },
  { href: "/scripts",      label: "Scripts",          icon: FileText,     tabKey: "Scripts",        hint: "Generate scripts" },
  { href: "/call-sheets",  label: "Call Sheets",      icon: Phone,        tabKey: "Call Sheets",    hint: "Shoot planning" },
  { href: "/titles",       label: "Titles",            icon: Image,        tabKey: "Titles",         hint: "Title cards" },
  { href: "/descriptions", label: "Descriptions",     icon: AlignLeft,    tabKey: "Descriptions",   hint: "SEO copy" },
  { href: "/compilations", label: "Compilations",     icon: Layers,       tabKey: "Compilations",   hint: "Comp builder" },
  { href: "/approvals",    label: "Approvals",         icon: CheckSquare,  tabKey: "Tickets",        hint: "Review queue" },
  { href: "/tickets",      label: "Tickets",            icon: Ticket,       tabKey: "Tickets",        hint: "Issue tracker" },
] as const

export default async function DashboardPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

  // Parallel fetch — all non-critical; failures degrade gracefully
  const [approvalRes, sceneStatsRes, ticketStatsRes, scriptsRes, notificationsRes, healthRes, userRes] =
    await Promise.allSettled([
      client.approvals.list("Pending"),
      client.scenes.stats(),
      client.tickets.stats(),
      client.scripts.list({ needs_script: true }),
      client.notifications.list(12),
      client.health(),
      client.users.me(),
    ])

  const pendingApprovals = approvalRes.status     === "fulfilled" ? approvalRes.value     : []
  const sceneStats       = sceneStatsRes.status   === "fulfilled" ? sceneStatsRes.value   : null
  const ticketStats      = ticketStatsRes.status  === "fulfilled" ? (ticketStatsRes.value as TicketStats) : {}
  const scriptsNeeded    = scriptsRes.status      === "fulfilled" ? scriptsRes.value      : []
  const notifications    = notificationsRes.status === "fulfilled" ? notificationsRes.value : []
  const health           = healthRes.status       === "fulfilled" ? healthRes.value       : null
  const userProfile      = userRes.status         === "fulfilled" ? userRes.value         : null

  const openTicketCount = Object.entries(ticketStats)
    .filter(([status]) => !["Closed", "Rejected"].includes(status))
    .reduce((sum, [, n]) => sum + n, 0)

  // Greeting
  const hour      = new Date().getHours()
  const greeting  = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
  const firstName = session?.user?.name?.split(" ")[0] ?? "there"
  const today     = new Date().toLocaleDateString("en-US", {
    weekday: "long", day: "numeric", month: "long",
  })

  // Module visibility — filtered by RBAC allowed_tabs
  const allowedTabs = userProfile?.allowed_tabs ?? "ALL"
  const userRole    = userProfile?.role ?? "editor"
  const allowedSet  = new Set(allowedTabs.split(",").map((t) => t.trim()))
  const visibleMods = (userRole === "admin" || allowedTabs === "ALL")
    ? ALL_MODULES
    : ALL_MODULES.filter((m) => allowedSet.has(m.tabKey))

  const unreadCount = notifications.filter((n) => n.read === 0).length
  const systemOk    = health !== null

  return (
    <div style={{ maxWidth: 1080 }}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div
        className="page-header"
        style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}
      >
        <div>
          <h1>{greeting}, {firstName}</h1>
          <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginTop: 3, letterSpacing: "0.03em" }}>
            {userRole.toUpperCase()} · {today}
          </p>
        </div>
        <div
          style={{
            fontSize: 11,
            color: "var(--color-text-faint)",
            display: "flex",
            alignItems: "center",
            gap: 5,
            paddingBottom: 2,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: systemOk ? "var(--color-ok)" : "var(--color-err)",
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          {systemOk ? "Systems nominal" : "API unreachable"}
        </div>
      </div>

      {/* ── Stat cards ─────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <StatCard
          label="Pending Approvals"
          value={pendingApprovals.length}
          href="/approvals"
          alert={pendingApprovals.length > 0}
        />
        <StatCard
          label="Missing Assets"
          value={sceneStats?.missing_any ?? "—"}
          context={sceneStats ? `of ${sceneStats.total} scenes` : undefined}
          href="/missing"
        />
        <StatCard
          label="Open Tickets"
          value={openTicketCount}
          href="/tickets"
          alert={openTicketCount > 5}
        />
        <StatCard
          label="Scripts Queued"
          value={scriptsNeeded.length}
          href="/scripts"
          accent="lime"
        />
      </div>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16, alignItems: "start" }}>

        {/* Left column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Studio breakdown */}
          {sceneStats && Object.keys(sceneStats.by_studio).length > 0 && (
            <PanelBlock label="Production Scope">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 28px" }}>
                {Object.entries(sceneStats.by_studio)
                  .sort(([, a], [, b]) => b - a)
                  .map(([studio, count]) => {
                    const color = studioColor(studio)
                    const abbr  = studioAbbr(studio)
                    const pct   = sceneStats.total > 0 ? (count / sceneStats.total) * 100 : 0
                    return (
                      <div key={studio}>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            marginBottom: 5,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span
                              style={{
                                width: 3,
                                height: 12,
                                borderRadius: 2,
                                background: color,
                                display: "inline-block",
                                flexShrink: 0,
                              }}
                            />
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                color,
                                letterSpacing: "0.05em",
                              }}
                            >
                              {abbr}
                            </span>
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", fontVariantNumeric: "tabular-nums" }}>
                            {count.toLocaleString()}
                            <span style={{ fontSize: 10, fontWeight: 400, color: "var(--color-text-faint)", marginLeft: 3 }}>
                              scenes
                            </span>
                          </span>
                        </div>
                        <div
                          style={{
                            height: 2,
                            background: "var(--color-border)",
                            borderRadius: 1,
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              height: "100%",
                              width: `${pct}%`,
                              background: color,
                              borderRadius: 1,
                              opacity: 0.7,
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}
              </div>
            </PanelBlock>
          )}

          {/* Quick access modules */}
          <PanelBlock label="Quick Access">
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
                gap: 8,
              }}
            >
              {visibleMods.map(({ href, label, icon: Icon, hint }) => (
                <Link
                  key={href}
                  href={href}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 5,
                    padding: "10px 11px",
                    background: "var(--color-elevated)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 5,
                    textDecoration: "none",
                    color: "inherit",
                  }}
                  className="hover:bg-[--color-border]"
                >
                  <Icon size={13} style={{ color: "var(--color-text-muted)" }} />
                  <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text)" }}>
                    {label}
                  </span>
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{hint}</span>
                </Link>
              ))}
            </div>
          </PanelBlock>

        </div>

        {/* Right column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Notifications — client component (needs mark-read state) */}
          <NotificationFeed
            initialNotifications={notifications}
            idToken={idToken}
            unreadCount={unreadCount}
          />

          {/* Sync status */}
          {health?.syncs && Object.keys(health.syncs).length > 0 && (
            <PanelBlock label="Sync Status">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {Object.entries(health.syncs).map(([source, infoRaw]) => {
                  const info = infoRaw as {
                    last_synced_at?: string
                    row_count?: number
                    status?: string
                    error?: string
                  }
                  const ok = !info.status || info.status === "ok" || info.status === "synced"
                  return (
                    <div key={source} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          flexShrink: 0,
                          background: ok ? "var(--color-ok)" : "var(--color-err)",
                        }}
                      />
                      <span style={{ flex: 1, fontSize: 12, color: "var(--color-text)" }}>
                        {source}
                      </span>
                      {info.row_count !== undefined && (
                        <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
                          {info.row_count.toLocaleString()} rows
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </PanelBlock>
          )}

        </div>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  context,
  href,
  alert,
  accent,
}: {
  label: string
  value: number | string
  context?: string
  href: string
  alert?: boolean
  accent?: "lime"
}) {
  const valueColor = alert
    ? "var(--color-warn)"
    : accent === "lime"
    ? "var(--color-lime)"
    : "var(--color-text)"

  const borderColor = alert
    ? "color-mix(in srgb, var(--color-warn) 28%, var(--color-border))"
    : "var(--color-border)"

  return (
    <Link
      href={href}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 5,
        padding: "14px 16px",
        background: "var(--color-surface)",
        border: `1px solid ${borderColor}`,
        borderRadius: 6,
        textDecoration: "none",
        color: "inherit",
        minHeight: 110,
      }}
      className="hover:bg-[--color-elevated]"
    >
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.07em",
          textTransform: "uppercase",
          color: "var(--color-text-faint)",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 30,
          fontWeight: 700,
          lineHeight: 1,
          color: valueColor,
          letterSpacing: "-0.03em",
          fontVariantNumeric: "tabular-nums",
          marginTop: 4,
        }}
      >
        {value}
      </span>
      {context && (
        <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{context}</span>
      )}
      <span
        style={{
          fontSize: 10,
          color: "var(--color-text-faint)",
          display: "flex",
          alignItems: "center",
          gap: 3,
          marginTop: "auto",
        }}
      >
        View <ArrowUpRight size={10} />
      </span>
    </Link>
  )
}

function PanelBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "9px 14px",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <h3 style={{ margin: 0 }}>{label}</h3>
      </div>
      <div style={{ padding: "12px 14px" }}>{children}</div>
    </div>
  )
}
