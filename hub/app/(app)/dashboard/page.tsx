import Link from "next/link"
import { auth } from "@/auth"
import { api, type Scene, type SceneStats, type Shoot } from "@/lib/api"
import { studioAbbr, STUDIO_COLOR } from "@/lib/studio-colors"
import { PageHeader } from "@/components/ui/page-header"
import { WeekCalendar } from "@/components/ui/week-calendar"
import { type Briefing, toneForCount } from "@/components/ui/today-briefing"
import { BriefingCache } from "./briefing-cache"
import { NotificationFeed } from "./notification-feed"
import { TriageFeed } from "./triage-feed"

export const dynamic = "force-dynamic"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

export default async function DashboardPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

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

  // Due Soon: scenes releasing within 14 days, derived from already-fetched data
  const dueSoon = recentScenes
    .filter(sc => {
      if (!sc.release_date) return false
      const diff = new Date(sc.release_date).getTime() - now.getTime()
      return diff >= 0 && diff <= 14 * 24 * 60 * 60 * 1000
    })
    .sort((a, b) => new Date(a.release_date).getTime() - new Date(b.release_date).getTime())
    .slice(0, 8)

  const briefing = computeBriefing({
    shoots,
    missingTotal: sceneStats?.missing_any ?? 0,
    scriptCount: scripts.length,
    shootsFetchFailed: shootsRes.status !== "fulfilled",
  })

  return (
    <div style={{ maxWidth: 1400 }}>
      <PageHeader
        compact
        title={`${greeting}, ${firstName}`}
        eyebrow={eyebrow}
        actions={
          !systemOk ? (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "var(--color-err)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: "var(--color-err)",
                  boxShadow: "0 0 0 3px color-mix(in srgb, var(--color-err) 20%, transparent)",
                }}
              />
              Connection lost
            </span>
          ) : undefined
        }
      />

      {/* ── KPI stats cluster ─────────────────────────────────────────── */}
      <div className="ec-stats" style={{ marginBottom: 20 }}>
        <div className="s">
          <div className="k">Scenes Live</div>
          <div className="v">{sceneStats?.total ?? "—"}</div>
          <div className="d">across all studios</div>
        </div>
        <div className="s">
          <div className="k">Shoots Active</div>
          <div className="v">{shoots.length || "—"}</div>
          <div className="d">in tracker</div>
        </div>
        <div className="s">
          <div className="k">Scripts Queued</div>
          <div className="v">{scripts.length || "—"}</div>
          <div className="d">need writing</div>
        </div>
        <div className="s">
          <div className="k">Missing Assets</div>
          <div className="v" style={sceneStats && sceneStats.missing_any > 0 ? { color: "var(--color-warn)" } : undefined}>
            {sceneStats?.missing_any ?? "—"}
          </div>
          <div className="d">scenes incomplete</div>
        </div>
      </div>

      <BriefingCache briefing={briefing} />

      {/* ── Body: Triage dominates (2/3), Notifications rail recedes ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">

        <div className="flex flex-col gap-6">
          {shoots.length > 0 && (
            <WeekCalendar shoots={shoots} flat />
          )}

          {sceneStats && Object.keys(sceneStats.by_studio).length > 0 && (
            <SceneCountStrip stats={sceneStats} />
          )}

          <TriageFeed
            recentScenes={recentScenes}
            missingTotal={sceneStats?.missing_any ?? 0}
            scripts={scripts}
            idToken={idToken}
          />

          {/* Closing tail — gives the page an ending instead of fading out. */}
          <div
            style={{
              marginTop: 4,
              paddingTop: 18,
              borderTop: "1px solid var(--color-border-subtle)",
              display: "flex",
              justifyContent: "flex-end",
            }}
          >
            <Link
              href="/missing"
              prefetch={false}
              style={{
                fontSize: 11,
                letterSpacing: "0.06em",
                color: "var(--color-text-faint)",
                textDecoration: "none",
              }}
              className="hover:text-[--color-text-muted]"
            >
              See the full catalog in Grail Assets →
            </Link>
          </div>
        </div>

        <div className="flex flex-col gap-3.5">
          {dueSoon.length > 0 && <DueSoonPanel scenes={dueSoon} />}
          <NotificationFeed
            initialNotifications={notifications}
            idToken={idToken}
            unreadCount={unreadCount}
          />
        </div>
      </div>
    </div>
  )
}

// ─── Today briefing computation ─────────────────────────────────────────────
//
// Single focal action for the dashboard. Picks the most urgent pending work
// and surfaces it as a hero line with one primary CTA. Everything else on the
// page is reference / browse. The briefing is the daily starting point.
//
// Tone ramps by magnitude via `toneForCount` so a single aging item doesn't
// wear the same red as 50. `error` tone short-circuits when the underlying
// fetch failed — we don't want to say "All clear" when we don't actually know.

function computeBriefing(input: {
  shoots: Shoot[]
  missingTotal: number
  scriptCount: number
  shootsFetchFailed?: boolean
}): Briefing {
  const { shoots, missingTotal, scriptCount, shootsFetchFailed } = input

  if (shootsFetchFailed) {
    return {
      tone: "error",
      count: 0,
      headline: "Can't reach the production server",
      detail: "Today's briefing couldn't be computed. Work is still reachable below, but urgency counts may be stale.",
      cta: null,
      secondary: [],
    }
  }

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
    const n = agingShoots.length
    return {
      tone: toneForCount(n),
      count: n,
      headline: `${n.toLocaleString()} shoot${n === 1 ? "" : "s"} stuck past 72h`,
      detail: n === 1
        ? "One shoot has incomplete assets more than three days after wrap."
        : `${n} shoots have incomplete assets more than three days after wrap.`,
      cta: { href: "/shoots", label: "Open shoots" },
      secondary: secondary.filter(s => !s.includes("stuck")),
    }
  }
  if (missingTotal >= 10) {
    return {
      tone: toneForCount(Math.min(missingTotal, 25)),
      count: missingTotal,
      headline: `${missingTotal.toLocaleString()} scenes need validation`,
      detail: "Assets are missing across the catalog. Triage the queue to clear the backlog.",
      cta: { href: "/missing", label: "Open triage" },
      secondary: secondary.filter(s => !s.includes("missing assets")),
    }
  }
  if (scriptCount > 0) {
    return {
      tone: toneForCount(scriptCount),
      count: scriptCount,
      headline: `${scriptCount} script${scriptCount === 1 ? "" : "s"} queued for writing`,
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

// ─── Sub-components ──────────────────────────────────────────────────────────

const STUDIO_ORDER = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

function DueSoonPanel({ scenes }: { scenes: Scene[] }) {
  return (
    <div className="ec-block" style={{ borderRadius: 0 }}>
      <header>
        <h2>Due Soon</h2>
        <div className="act">
          <Link href="/missing" prefetch={false} style={{ textDecoration: "none" }}>All →</Link>
        </div>
      </header>
      <div>
        {scenes.map(sc => {
          const relDate = new Date(sc.release_date)
          const daysLeft = Math.ceil((relDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
          const studioColor = STUDIO_COLOR[sc.studio] ?? "var(--color-text-muted)"
          return (
            <div
              key={sc.id}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "7px 16px", borderBottom: "1px solid var(--color-border-subtle)",
                gap: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {sc.title}
                </div>
                <div style={{ fontSize: 10, color: studioColor, letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 2 }}>
                  {sc.site_code ?? studioAbbr(sc.studio)}
                </div>
              </div>
              <div
                style={{
                  fontSize: 10, fontWeight: 700, whiteSpace: "nowrap",
                  color: daysLeft <= 3 ? "var(--color-err)" : daysLeft <= 7 ? "var(--color-warn)" : "var(--color-text-muted)",
                }}
              >
                {daysLeft}d
              </div>
            </div>
          )
        })}
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
        const isNjoi = studio === "NaughtyJOI"
        const key = studioAbbr(studio).toLowerCase()
        return (
          <div key={studio} className={`cell ${key}`} style={isNjoi ? { opacity: 0.45 } : undefined}>
            <div className="mono">{studioAbbr(studio)}</div>
            <div className="big" style={isNjoi ? { fontSize: "1.5rem" } : undefined}>{count.toLocaleString()}<sup>SCN</sup></div>
            <div className="bar" style={{ width: `${Math.round((count / max) * 100)}%` }} />
          </div>
        )
      })}
    </div>
  )
}


