import Link from "next/link"
import { type Shoot } from "@/lib/api"
import { studioAbbr } from "@/lib/studio-colors"
import { WeekCalendar } from "@/components/ui/week-calendar"
import { type Briefing, toneForCount } from "@/components/ui/today-briefing"
import { BriefingCache } from "./briefing-cache"
import { NotificationFeed } from "./notification-feed"
import { TriageFeed } from "./triage-feed"
import {
  getHealthOk,
  getNotifications,
  getRecentScenes,
  getSceneStats,
  getScripts,
  getShoots,
} from "./data"

const STUDIO_ORDER = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

// ─── Health badge in PageHeader actions slot ────────────────────────────────

export async function HealthBadge({ idToken }: { idToken: string | undefined }) {
  const ok = await getHealthOk(idToken)
  if (ok) return null
  return (
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
  )
}

// ─── Today briefing ─────────────────────────────────────────────────────────

export async function BriefingSection({ idToken }: { idToken: string | undefined }) {
  const [{ shoots, failed }, sceneStats, scripts] = await Promise.all([
    getShoots(idToken),
    getSceneStats(idToken),
    getScripts(idToken),
  ])
  const briefing = computeBriefing({
    shoots,
    missingTotal: sceneStats?.missing_any ?? 0,
    scriptCount: scripts.length,
    shootsFetchFailed: failed,
  })
  return <BriefingCache briefing={briefing} />
}

// ─── Week calendar ──────────────────────────────────────────────────────────

export async function CalendarSection({ idToken }: { idToken: string | undefined }) {
  const { shoots } = await getShoots(idToken)
  if (shoots.length === 0) return null
  return (
    <div style={{ marginBottom: 20 }}>
      <WeekCalendar shoots={shoots} flat />
    </div>
  )
}

// ─── Scene-count strip ──────────────────────────────────────────────────────

export async function SceneStripSection({ idToken }: { idToken: string | undefined }) {
  const stats = await getSceneStats(idToken)
  if (!stats || Object.keys(stats.by_studio).length === 0) return null
  const entries = STUDIO_ORDER
    .map(s => [s, stats.by_studio[s] ?? 0] as [string, number])
    .filter(([, n]) => n > 0)
  const max = Math.max(1, ...entries.map(([, n]) => n))
  return (
    <div style={{ marginBottom: 20 }}>
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
    </div>
  )
}

// ─── Triage feed (recent scenes + scripts queue) ─────────────────────────────

export async function TriageSection({ idToken }: { idToken: string | undefined }) {
  const [recentScenes, scripts, sceneStats] = await Promise.all([
    getRecentScenes(idToken),
    getScripts(idToken),
    getSceneStats(idToken),
  ])
  // Captured at section render time so the client can show "updated Ns ago"
  // off the actual fetch boundary, not the moment React hydrated.
  const generatedAt = Date.now()
  return (
    <>
      <TriageFeed
        recentScenes={recentScenes}
        missingTotal={sceneStats?.missing_any ?? 0}
        scripts={scripts}
        idToken={idToken}
        generatedAt={generatedAt}
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
    </>
  )
}

// ─── Notifications rail ─────────────────────────────────────────────────────

export async function NotificationSection({ idToken }: { idToken: string | undefined }) {
  const notifications = await getNotifications(idToken)
  const unreadCount = notifications.filter((n) => n.read === 0).length
  return (
    <NotificationFeed
      initialNotifications={notifications}
      idToken={idToken}
      unreadCount={unreadCount}
    />
  )
}

// ─── Skeletons ──────────────────────────────────────────────────────────────

export function BriefingSkeleton() {
  return (
    <section
      aria-label="Loading today briefing"
      aria-busy="true"
      style={{
        marginBottom: 28,
        paddingBottom: 20,
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "grid",
        gridTemplateColumns: "auto minmax(0, 1fr) auto",
        alignItems: "center",
        gap: 20,
        minHeight: 88,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <SkelBar w={48} h={9} />
        <SkelBar w={64} h={48} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
        <SkelBar w={"60%"} h={18} />
        <SkelBar w={"45%"} h={12} />
      </div>
      <SkelBar w={120} h={36} />
    </section>
  )
}

export function CalendarSkeleton() {
  return (
    <div style={{ marginBottom: 20, minHeight: 132 }} aria-busy="true">
      <SkelBar w={"100%"} h={132} />
    </div>
  )
}

export function StripSkeleton() {
  return (
    <div style={{ marginBottom: 20, minHeight: 76 }} aria-busy="true">
      <SkelBar w={"100%"} h={76} />
    </div>
  )
}

export function TriageSkeleton() {
  return (
    <div
      aria-busy="true"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
        minHeight: 280,
      }}
    >
      <div style={{ padding: "9px 14px", borderBottom: "1px solid var(--color-border)" }}>
        <SkelBar w={140} h={14} />
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          style={{
            padding: "10px 14px",
            borderBottom: "1px solid var(--color-border-subtle)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <SkelBar w={32} h={14} />
          <SkelBar w={70} h={12} />
          <SkelBar w={"50%"} h={12} />
        </div>
      ))}
    </div>
  )
}

export function NotificationSkeleton() {
  return (
    <div
      aria-busy="true"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
        minHeight: 220,
      }}
    >
      <div style={{ padding: "9px 14px", borderBottom: "1px solid var(--color-border)" }}>
        <SkelBar w={100} h={14} />
      </div>
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          style={{
            padding: "10px 14px",
            borderBottom: "1px solid var(--color-border-subtle)",
            display: "flex",
            gap: 10,
          }}
        >
          <SkelBar w={12} h={12} />
          <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
            <SkelBar w={"75%"} h={10} />
            <SkelBar w={"55%"} h={8} />
          </div>
        </div>
      ))}
    </div>
  )
}

function SkelBar({ w, h }: { w: number | string; h: number }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-block",
        width: w,
        height: h,
        borderRadius: 3,
        background: "linear-gradient(90deg, var(--color-elevated) 0%, var(--color-border) 50%, var(--color-elevated) 100%)",
        backgroundSize: "200% 100%",
        animation: "skeletonShimmer 1400ms linear infinite",
      }}
    />
  )
}

// ─── Briefing computation (moved from page.tsx) ─────────────────────────────

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
