import { Suspense } from "react"
import Link from "next/link"
import { auth } from "@/auth"
import type { Session } from "next-auth"
import { api, type SceneStats, type Shoot } from "@/lib/api"
import { studioAbbr } from "@/lib/studio-colors"
import { PageHeader } from "@/components/ui/page-header"
import { WeekCalendar } from "@/components/ui/week-calendar"
import { SkeletonBar } from "@/components/ui/skeleton"
import { type Briefing, toneForCount } from "@/components/ui/today-briefing"
import { BriefingCache } from "./briefing-cache"
import { NotificationFeed } from "./notification-feed"
import { TriageFeed } from "./triage-feed"

export const dynamic = "force-dynamic"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

export default async function DashboardPage() {
  const session = await auth()
  const now       = new Date()
  const hour      = now.getHours()
  const greeting  = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
  const firstName = session?.user?.name?.split(" ")[0] ?? "there"
  const eyebrow = now
    .toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
    .toUpperCase()

  return (
    <div style={{ maxWidth: 1400 }}>
      {/* Header renders immediately — no API calls needed */}
      <PageHeader compact title={`${greeting}, ${firstName}`} eyebrow={eyebrow} />

      {/* Data body streams in — shell + greeting visible while APIs load */}
      <Suspense fallback={<DashboardBodySkeleton />}>
        <DashboardBody session={session} />
      </Suspense>
    </div>
  )
}

// ─── Streaming body ──────────────────────────────────────────────────────────

async function DashboardBody({ session }: { session: Session | null }) {
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

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

  const unreadCount = notifications.filter((n) => n.read === 0).length
  const systemOk    = health !== null

  const briefing = computeBriefing({
    shoots,
    missingTotal: sceneStats?.missing_any ?? 0,
    scriptCount: scripts.length,
    shootsFetchFailed: shootsRes.status !== "fulfilled",
  })

  return (
    <>
      <BriefingCache briefing={briefing} />

      {!systemOk && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 12,
            color: "var(--color-err)",
            marginBottom: 12,
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
        </div>
      )}

      {shoots.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <WeekCalendar shoots={shoots} flat />
        </div>
      )}

      {sceneStats && Object.keys(sceneStats.by_studio).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <SceneCountStrip stats={sceneStats} />
        </div>
      )}

      {/* ── Body: Triage dominates (2/3), Notifications rail ────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">

        <div className="flex flex-col gap-6">
          <TriageFeed
            recentScenes={recentScenes}
            missingTotal={sceneStats?.missing_any ?? 0}
            scripts={scripts}
            idToken={idToken}
          />

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
          <NotificationFeed
            initialNotifications={notifications}
            idToken={idToken}
            unreadCount={unreadCount}
          />
        </div>
      </div>
    </>
  )
}

// ─── Body skeleton shown while DashboardBody fetches ─────────────────────────

function DashboardBodySkeleton() {
  return (
    <>
      <div
        style={{
          padding: "14px 16px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          marginBottom: 20,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <SkeletonBar width={200} height={14} />
        <SkeletonBar width={320} height={10} />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 8,
          marginBottom: 20,
        }}
      >
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            style={{
              padding: "12px 14px",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              opacity: 1 - i * 0.12,
            }}
          >
            <SkeletonBar width={40} height={9} />
            <SkeletonBar width={70} height={22} />
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 24 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {[90, 75, 85, 65, 80].map((w, i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 5,
                display: "flex",
                gap: 10,
                alignItems: "center",
                opacity: 1 - i * 0.1,
              }}
            >
              <SkeletonBar width={56} height={40} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                <SkeletonBar width={`${w}%`} height={11} />
                <SkeletonBar width="50%" height={9} />
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 5,
                display: "flex",
                gap: 8,
                alignItems: "flex-start",
                opacity: 1 - i * 0.12,
              }}
            >
              <SkeletonBar width={13} height={13} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 5 }}>
                <SkeletonBar width="80%" height={10} />
                <SkeletonBar width="60%" height={9} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

// ─── Today briefing computation ─────────────────────────────────────────────

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
