import Link from "next/link"
import { AlertTriangle } from "lucide-react"
import { auth } from "@/auth"
import { api, type Scene, type SceneStats, type Shoot } from "@/lib/api"
import { studioColor, studioAbbr } from "@/lib/studio-colors"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { PageHeader } from "@/components/ui/page-header"
import { Panel } from "@/components/ui/panel"
import { WeekCalendar } from "@/components/ui/week-calendar"
import { NotificationFeed } from "./notification-feed"
import { TriageFeed } from "./triage-feed"

export const dynamic = "force-dynamic"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

export default async function DashboardPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken
  const v2 = await isEclatechV2()

  // Approvals removed from the dashboard for now — the team isn't using
  // the approvals workflow yet. The /approvals route + API are gone too;
  // bring them back via git when the workflow's needed.
  const [
    sceneStatsRes,
    scriptsRes,
    notificationsRes,
    healthRes,
    shootsRes,
    ...missingResults
  ] = await Promise.allSettled([
    client.scenes.stats(),
    client.scripts.list({ needs_script: true }),
    client.notifications.list(12),
    client.health(),
    client.shoots.list(),
    ...STUDIOS.map(s => client.scenes.list({ studio: s, limit: 5 })),
  ])

  const sceneStats     = sceneStatsRes.status    === "fulfilled" ? sceneStatsRes.value    : null
  const scripts        = scriptsRes.status       === "fulfilled" ? scriptsRes.value       : []
  const notifications  = notificationsRes.status === "fulfilled" ? notificationsRes.value : []
  const health         = healthRes.status        === "fulfilled" ? healthRes.value        : null
  const shoots         = shootsRes.status        === "fulfilled" ? shootsRes.value        : []

  const recentScenes = missingResults
    .flatMap(r => r.status === "fulfilled" ? r.value : [])

  const now       = new Date()
  const hour      = now.getHours()
  const greeting  = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
  const firstName = session?.user?.name?.split(" ")[0] ?? "there"
  const unreadCount = notifications.filter((n) => n.read === 0).length
  const systemOk    = health !== null

  // Mono-style timecode eyebrow — echoes the backstage/production vibe
  const eyebrow = now
    .toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
    .toUpperCase()

  const briefing = computeBriefing({
    shoots,
    missingTotal: sceneStats?.missing_any ?? 0,
    scriptCount: scripts.length,
  })

  return (
    <div style={{ maxWidth: 1400 }}>
      <PageHeader
        title={`${greeting}, ${firstName}`}
        eyebrow={eyebrow}
        actions={
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              color: systemOk ? "var(--color-text-muted)" : "var(--color-err)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: systemOk ? "var(--color-ok)" : "var(--color-err)",
                boxShadow: systemOk
                  ? "0 0 0 3px color-mix(in srgb, var(--color-ok) 20%, transparent)"
                  : "0 0 0 3px color-mix(in srgb, var(--color-err) 20%, transparent)",
              }}
            />
            {systemOk ? "All green" : "Connection lost"}
          </span>
        }
      />

      <TodayBriefing briefing={briefing} />

      {/* ── Body: Triage dominates (2/3), Notifications rail recedes ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">

        <div className="flex flex-col gap-6">
          {v2 && shoots.length > 0 && (
            <WeekCalendar shoots={shoots} flat />
          )}

          {sceneStats && Object.keys(sceneStats.by_studio).length > 0 && (
            v2
              ? <SceneCountStrip stats={sceneStats} />
              : <ProductionScopeStrip stats={sceneStats} />
          )}

          <TriageFeed
            recentScenes={recentScenes}
            missingTotal={sceneStats?.missing_any ?? 0}
            scripts={scripts}
            idToken={idToken}
          />
        </div>

        <div className="flex flex-col gap-3.5">
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

// ─── Today briefing ─────────────────────────────────────────────────────────
//
// Single focal action for the dashboard. Computes the most urgent pending work
// and surfaces it as a hero line with one primary CTA. Everything else on the
// page is reference / browse. The briefing is the daily starting point.

type BriefingTone = "urgent" | "attention" | "calm"
interface Briefing {
  tone: BriefingTone
  count: number
  headline: string
  detail: string
  cta: { href: string; label: string } | null
  secondary: string[]
}

function computeBriefing(input: {
  shoots: Shoot[]
  missingTotal: number
  scriptCount: number
}): Briefing {
  const { shoots, missingTotal, scriptCount } = input
  const agingShoots = shoots.filter(s => {
    if (s.aging_hours < 72) return false
    let validated = 0, total = 0
    for (const sc of s.scenes) for (const a of sc.assets) { total += 1; if (a.status === "validated") validated += 1 }
    return total > 0 && validated < total
  })

  const secondary: string[] = []
  if (missingTotal > 0) secondary.push(`${missingTotal.toLocaleString()} scenes missing assets`)
  if (scriptCount > 0) secondary.push(`${scriptCount} script${scriptCount === 1 ? "" : "s"} queued`)
  if (agingShoots.length > 0) secondary.push(`${agingShoots.length} stuck shoot${agingShoots.length === 1 ? "" : "s"}`)

  if (agingShoots.length > 0) {
    return {
      tone: "urgent",
      count: agingShoots.length,
      headline: `shoot${agingShoots.length === 1 ? "" : "s"} stuck past 72h`,
      detail: agingShoots.length === 1
        ? "One shoot has incomplete assets more than three days after wrap."
        : `${agingShoots.length} shoots have incomplete assets more than three days after wrap.`,
      cta: { href: "/shoots", label: "Open shoots" },
      secondary: secondary.filter(s => !s.includes("stuck")),
    }
  }
  if (missingTotal >= 10) {
    return {
      tone: "attention",
      count: missingTotal,
      headline: "scenes need validation",
      detail: "Assets are missing across the catalog. Triage the queue to clear the backlog.",
      cta: { href: "/missing", label: "Open triage" },
      secondary: secondary.filter(s => !s.includes("missing assets")),
    }
  }
  if (scriptCount > 0) {
    return {
      tone: "attention",
      count: scriptCount,
      headline: `script${scriptCount === 1 ? "" : "s"} queued for writing`,
      detail: "Scripts are ready to be drafted before their shoot dates.",
      cta: { href: "/scripts", label: "Start writing" },
      secondary: secondary.filter(s => !s.includes("queued")),
    }
  }
  return {
    tone: "calm",
    count: 0,
    headline: "All clear",
    detail: "Nothing urgent is on deck. Browse recent activity below.",
    cta: null,
    secondary,
  }
}

function TodayBriefing({ briefing }: { briefing: Briefing }) {
  const accentColor =
    briefing.tone === "urgent" ? "var(--color-err)"
    : briefing.tone === "attention" ? "var(--color-warn)"
    : "var(--color-text-muted)"

  return (
    <section
      aria-label="Today"
      className="today-briefing"
      style={{
        marginBottom: 28,
        display: "grid",
        gridTemplateColumns: "auto minmax(0, 1fr) auto",
        alignItems: "center",
        gap: 20,
        paddingBottom: 20,
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--color-text-faint)",
          }}
        >
          Today
        </div>
        <div
          style={{
            fontFamily: "var(--font-display-hero)",
            fontWeight: 400,
            fontSize: briefing.count > 0 ? 64 : 44,
            lineHeight: 0.95,
            letterSpacing: "-0.02em",
            color: briefing.count > 0 ? accentColor : "var(--color-text)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {briefing.count > 0 ? briefing.count.toLocaleString() : "✓"}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
        <div
          style={{
            fontSize: "var(--text-title)",
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: "var(--color-text)",
            lineHeight: 1.25,
          }}
        >
          {briefing.count > 0 ? `${briefing.count.toLocaleString()} ${briefing.headline}` : briefing.headline}
        </div>
        <div
          style={{
            fontSize: 13,
            color: "var(--color-text-muted)",
            maxWidth: "65ch",
            lineHeight: 1.45,
          }}
        >
          {briefing.detail}
        </div>
        {briefing.secondary.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
              marginTop: 2,
              fontSize: 11,
              color: "var(--color-text-faint)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {briefing.secondary.map((s, i) => (
              <span key={i}>{i > 0 && <span style={{ marginRight: 6, opacity: 0.5 }}>·</span>}{s}</span>
            ))}
          </div>
        )}
      </div>

      {briefing.cta && (
        <Link
          href={briefing.cta.href}
          prefetch={false}
          style={{
            background: "var(--color-lime)",
            color: "var(--color-lime-ink)",
            padding: "10px 18px",
            borderRadius: 4,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: "0.02em",
            textDecoration: "none",
            whiteSpace: "nowrap",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {briefing.cta.label} <span aria-hidden="true">→</span>
        </Link>
      )}
    </section>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

const STUDIO_ORDER = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

function UpcomingShootStats({ shoots }: { shoots: Shoot[] }) {
  const now = new Date()
  const weekStart = new Date(now)
  weekStart.setHours(0, 0, 0, 0)
  weekStart.setDate(weekStart.getDate() - weekStart.getDay())
  const weekEnd = new Date(weekStart)
  weekEnd.setDate(weekEnd.getDate() + 7)

  const thisWeek = shoots.filter(s => {
    const t = Date.parse(s.shoot_date || "")
    return Number.isFinite(t) && t >= weekStart.getTime() && t < weekEnd.getTime()
  })

  const scenesCount = thisWeek.reduce((sum, s) => sum + s.scenes.length, 0)

  const talentSet = new Set<string>()
  for (const s of thisWeek) {
    if (s.female_talent) talentSet.add(s.female_talent.trim().toLowerCase())
    if (s.male_talent)   talentSet.add(s.male_talent.trim().toLowerCase())
  }

  const studioSet = new Set<string>()
  for (const s of thisWeek) for (const sc of s.scenes) studioSet.add(sc.studio)
  const activeStudioAbbrs = Array.from(studioSet)
    .map(s => studioAbbr(s))
    .sort()

  const shootDays = new Set(thisWeek.map(s => s.shoot_date.slice(0, 10))).size

  return (
    <div className="ec-stats">
      <div className="s">
        <div className="k">Shoots</div>
        <div className="v">{thisWeek.length}<span className="unit">scheduled</span></div>
        <div className="d">{shootDays} shoot day{shootDays === 1 ? "" : "s"}</div>
      </div>
      <div className="s">
        <div className="k">Scenes</div>
        <div className="v">{scenesCount}</div>
        <div className="d">to produce</div>
      </div>
      <div className="s">
        <div className="k">Talent</div>
        <div className="v">{talentSet.size}</div>
        <div className="d">on set</div>
      </div>
      <div className="s">
        <div className="k">Studios</div>
        <div className="v">{activeStudioAbbrs.length}</div>
        <div className="d">{activeStudioAbbrs.length > 0 ? activeStudioAbbrs.join(" · ") : "None"}</div>
      </div>
    </div>
  )
}

function SceneCountStrip({ stats }: { stats: SceneStats }) {
  const entries = STUDIO_ORDER
    .map(s => [s, stats.by_studio[s] ?? 0] as [string, number])
    .filter(([, n]) => n > 0)
  const max = Math.max(1, ...entries.map(([, n]) => n))
  return (
    <div className="ec-strip">
      <div className="label">Scene Count</div>
      {entries.slice(0, 4).map(([studio, count]) => {
        const key = studioAbbr(studio).toLowerCase()
        return (
          <div key={studio} className={`cell ${key}`}>
            <div className="mono">{studioAbbr(studio)}</div>
            <div className="big">{count.toLocaleString()}<sup>SCN</sup></div>
            <div className="bar" style={{ width: `${Math.round((count / max) * 100)}%` }} />
          </div>
        )
      })}
    </div>
  )
}

function DueSoonPanel({ scenes }: { scenes: Scene[] }) {
  const now = Date.now()
  const WEEK = 7 * 24 * 60 * 60 * 1000
  const upcoming = scenes
    .filter(s => {
      const t = Date.parse(s.release_date || "")
      if (!Number.isFinite(t)) return false
      const delta = t - now
      return delta > -WEEK && delta < WEEK * 2 // -7d through +14d
    })
    .sort((a, b) => (a.release_date ?? "").localeCompare(b.release_date ?? ""))
    .slice(0, 6)

  return (
    <Panel
      title="Due Soon"
      count={upcoming.length > 0 ? upcoming.length : undefined}
      action={
        <Link href="/missing" style={{ fontSize: 10, color: "var(--color-text-faint)", textDecoration: "none" }}>
          All missing →
        </Link>
      }
    >
      {upcoming.length === 0 ? (
        <div style={{ padding: "16px 14px", textAlign: "center", color: "var(--color-text-faint)", fontSize: 12 }}>
          Nothing on deck ✓
        </div>
      ) : (
        <div>
          {upcoming.map((s, i) => {
            const accent = studioColor(s.studio)
            const missingBits: string[] = []
            if (!s.has_videos) missingBits.push("videos")
            if (!s.has_thumbnail) missingBits.push("thumb")
            if (!s.has_description) missingBits.push("desc")
            if (!s.has_photos) missingBits.push("photos")
            return (
              <Link
                key={s.id}
                href={`/missing?scene=${encodeURIComponent(s.id)}`}
                className="hover:bg-[--color-elevated]"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 14px",
                  borderBottom: i < upcoming.length - 1 ? "1px solid var(--color-border-subtle, var(--color-border))" : undefined,
                  textDecoration: "none",
                  color: "inherit",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--color-text)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <span style={{ fontFamily: "var(--font-mono)", color: accent, fontWeight: 700, marginRight: 8 }}>{s.id}</span>
                    {s.female && <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>{s.female}{s.male ? ` / ${s.male}` : ""}</span>}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
                    {s.release_date}
                    {missingBits.length > 0 && <span style={{ color: "var(--color-err)" }}> · missing {missingBits.join(", ")}</span>}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </Panel>
  )
}

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
    <Panel
      title="Aging Shoots"
      count={aging.length > 0 ? aging.length : undefined}
      tone={aging.length > 0 ? "urgent" : "default"}
      action={
        <Link href="/shoots" style={{ fontSize: 10, color: "var(--color-text-faint)", textDecoration: "none" }}>
          All shoots →
        </Link>
      }
    >
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
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--color-text)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {primaryStudio && (
                      <span style={{ fontFamily: "var(--font-mono)", color: accent, fontWeight: 700, marginRight: 8, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                        {primaryStudio.slice(0, 4)}
                      </span>
                    )}
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
    </Panel>
  )
}

function SyncStatusPanel({ syncs }: { syncs: Record<string, unknown> }) {
  return (
    <Panel title="Sync Status">
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
    </Panel>
  )
}
