import Link from "next/link"
import { AlertTriangle } from "lucide-react"
import { auth } from "@/auth"
import { api, type SceneStats, type Shoot } from "@/lib/api"
import { studioColor, studioAbbr } from "@/lib/studio-colors"
import { NotificationFeed } from "./notification-feed"
import { TriageFeed } from "./triage-feed"

export const dynamic = "force-dynamic"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

export default async function DashboardPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

  const [
    approvalRes,
    sceneStatsRes,
    scriptsRes,
    notificationsRes,
    healthRes,
    shootsRes,
    ...missingResults
  ] = await Promise.allSettled([
    client.approvals.list("Pending"),
    client.scenes.stats(),
    client.scripts.list({ needs_script: true }),
    client.notifications.list(12),
    client.health(),
    client.shoots.list(),
    ...STUDIOS.map(s => client.scenes.list({ studio: s, limit: 3, missing_only: true })),
  ])

  const approvals      = approvalRes.status      === "fulfilled" ? approvalRes.value      : []
  const sceneStats     = sceneStatsRes.status    === "fulfilled" ? sceneStatsRes.value    : null
  const scripts        = scriptsRes.status       === "fulfilled" ? scriptsRes.value       : []
  const notifications  = notificationsRes.status === "fulfilled" ? notificationsRes.value : []
  const health         = healthRes.status        === "fulfilled" ? healthRes.value        : null
  const shoots         = shootsRes.status        === "fulfilled" ? shootsRes.value        : []

  const missingScenes = missingResults
    .flatMap(r => r.status === "fulfilled" ? r.value : [])
    .sort((a, b) => (b.release_date ?? "").localeCompare(a.release_date ?? ""))

  const hour      = new Date().getHours()
  const greeting  = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
  const firstName = session?.user?.name?.split(" ")[0] ?? "there"
  const unreadCount = notifications.filter((n) => n.read === 0).length
  const systemOk    = health !== null

  return (
    <div style={{ maxWidth: 1200 }}>
      {/* ── Condensed header ─────────────────────────────────────────────── */}
      <div className="page-header" style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>
          {greeting}, {firstName}
        </h1>
        <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--color-text-faint)" }}>
          <span
            aria-hidden="true"
            style={{
              width: 6, height: 6, borderRadius: "50%",
              background: systemOk ? "var(--color-ok)" : "var(--color-err)",
              display: "inline-block", flexShrink: 0,
            }}
          />
          {systemOk ? "All green" : "Connection lost"}
        </span>
      </div>

      {/* ── Body: Triage dominates (2/3), Notifications rail recedes ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-5 items-start">

        <div className="flex flex-col gap-3.5">
          {sceneStats && Object.keys(sceneStats.by_studio).length > 0 && (
            <ProductionScopeStrip stats={sceneStats} />
          )}

          <TriageFeed
            initialApprovals={approvals}
            missingScenes={missingScenes}
            missingTotal={sceneStats?.missing_any ?? 0}
            scripts={scripts}
            idToken={idToken}
          />
        </div>

        <div className="flex flex-col gap-3.5">
          <AgingShootsPanel shoots={shoots} />

          <NotificationFeed
            initialNotifications={notifications}
            idToken={idToken}
            unreadCount={unreadCount}
          />

          {health?.syncs && Object.keys(health.syncs).length > 0 && (
            <SyncStatusPanel syncs={health.syncs} />
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ProductionScopeStrip({ stats }: { stats: SceneStats }) {
  const entries = Object.entries(stats.by_studio).sort(([, a], [, b]) => b - a)
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        padding: "8px 14px",
        display: "flex",
        alignItems: "center",
        gap: 18,
        flexWrap: "wrap",
      }}
    >
      <span style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-faint)", letterSpacing: "0.07em", textTransform: "uppercase" }}>
        Production
      </span>
      {entries.map(([studio, count]) => {
        const color = studioColor(studio)
        const abbr  = studioAbbr(studio)
        return (
          <span key={studio} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span aria-hidden="true" style={{ width: 2, height: 10, background: color, borderRadius: 1, display: "inline-block" }} />
            <span style={{ fontWeight: 700, color, letterSpacing: "0.04em" }}>{abbr}</span>
            <span style={{ fontVariantNumeric: "tabular-nums", color: "var(--color-text)" }}>
              {count.toLocaleString()}
            </span>
          </span>
        )
      })}
      <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--color-text-faint)" }}>
        {stats.total.toLocaleString()} scenes · {stats.missing_any} missing
      </span>
    </div>
  )
}

// Shoots past their completion window that still have gaps. Threshold is
// generous (72h) so an in-progress-today shoot doesn't clutter the list.
const AGING_THRESHOLD_HOURS = 72

function AgingShootsPanel({ shoots }: { shoots: Shoot[] }) {
  const aging = shoots
    .filter(s => {
      if (s.aging_hours < AGING_THRESHOLD_HOURS) return false
      // Count cells — if validated === total, the shoot is done
      let validated = 0
      let total = 0
      for (const sc of s.scenes) {
        for (const a of sc.assets) {
          total += 1
          if (a.status === "validated") validated += 1
        }
      }
      return total > 0 && validated < total
    })
    .sort((a, b) => b.aging_hours - a.aging_hours)
    .slice(0, 5)

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
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <h3 style={{ margin: 0 }}>Aging Shoots</h3>
          {aging.length > 0 && (
            <span
              aria-label={`${aging.length} shoots need attention`}
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: "var(--color-err)",
                border: "1px solid color-mix(in srgb, var(--color-err) 28%, transparent)",
                background: "color-mix(in srgb, var(--color-err) 10%, transparent)",
                borderRadius: 10,
                padding: "0 6px",
                lineHeight: 1.5,
              }}
            >
              {aging.length}
            </span>
          )}
        </div>
        <Link href="/shoots" style={{ fontSize: 10, color: "var(--color-text-faint)", textDecoration: "none" }}>
          All shoots →
        </Link>
      </div>

      {aging.length === 0 ? (
        <div style={{ padding: "16px 14px", textAlign: "center", color: "var(--color-text-faint)", fontSize: 12 }}>
          Nothing stuck past 72h ✓
        </div>
      ) : (
        <div>
          {aging.map((s, i) => {
            let validated = 0, total = 0
            for (const sc of s.scenes) {
              for (const a of sc.assets) {
                total += 1
                if (a.status === "validated") validated += 1
              }
            }
            const days = Math.floor(s.aging_hours / 24)
            const primaryStudio = s.scenes[0]?.studio ?? ""
            const accent = primaryStudio ? studioColor(primaryStudio) : "var(--color-text-muted)"
            return (
              <Link
                key={s.shoot_id}
                href="/shoots"
                className="hover:bg-[--color-elevated]"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 14px",
                  borderBottom: i < aging.length - 1 ? "1px solid var(--color-border-subtle, var(--color-border))" : undefined,
                  textDecoration: "none",
                  color: "inherit",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{ width: 2, height: 22, background: accent, borderRadius: 1, flexShrink: 0 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--color-text)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {s.female_talent}
                    {s.male_talent && <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}> / {s.male_talent}</span>}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
                    {days}d old · {validated}/{total} done
                  </div>
                </div>
                <AlertTriangle size={12} style={{ color: "var(--color-err)", flexShrink: 0 }} aria-hidden="true" />
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

function SyncStatusPanel({ syncs }: { syncs: Record<string, unknown> }) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "9px 14px", borderBottom: "1px solid var(--color-border)" }}>
        <h3 style={{ margin: 0 }}>Sync Status</h3>
      </div>
      <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
        {Object.entries(syncs).map(([source, infoRaw]) => {
          const info = infoRaw as { last_synced_at?: string; row_count?: number; status?: string; error?: string }
          const ok = !info.status || info.status === "ok" || info.status === "synced"
          return (
            <div key={source} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                aria-hidden="true"
                style={{
                  width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                  background: ok ? "var(--color-ok)" : "var(--color-err)",
                }}
              />
              <span style={{ flex: 1, fontSize: 12, color: "var(--color-text)" }}>{source}</span>
              {info.row_count !== undefined && (
                <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
                  {info.row_count.toLocaleString()} rows
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
