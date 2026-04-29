"use client"

import type { Scene, SceneStats } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { TodayBriefing, type Briefing } from "@/components/ui/today-briefing"
import { studioAbbr, studioColor } from "@/lib/studio-colors"
import { parseLocalDate } from "@/lib/dates"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const

/** Prototype-style overview for Grail Assets. Owns the hero title, then
 *  renders a "Next up" briefing + stat cluster + studio strip. SceneGrid
 *  below keeps its own filter actions but its duplicate title block is
 *  hidden via CSS. */
export function MissingV2View({
  stats,
  scenes = [],
  fetchFailed = false,
  sceneSyncedAt = null,
}: {
  stats: SceneStats
  scenes?: Scene[]
  fetchFailed?: boolean
  sceneSyncedAt?: string | null
}) {
  const totalMissing = stats.missing_any
  const complete = stats.complete
  const total = stats.total
  const completePct = total > 0 ? Math.round((complete / total) * 100) : 0

  const briefing = computeMissingBriefing({ scenes, totalMissing, fetchFailed })

  return (
    <div style={{ marginBottom: 20 }}>
      <PageHeader
        title="Grail Assets"
        eyebrow={`STUDIO CATALOG · ${totalMissing.toLocaleString()} SCENES NEED WORK`}
        subtitle={`${complete.toLocaleString()} of ${total.toLocaleString()} scenes complete · ${completePct}% of the catalog`}
      />

      <TodayBriefing briefing={briefing} />

      {/* KPI stat cluster */}
      <div className="ec-stats">
        <div className="s">
          <div className="k">TOTAL SCENES</div>
          <div className="v">{total.toLocaleString()}</div>
        </div>
        <div className="s">
          <div className="k">COMPLETE</div>
          <div className="v">{complete.toLocaleString()}</div>
          <div className="d">{completePct}% of catalog</div>
        </div>
        <div className="s">
          <div className="k">MISSING</div>
          <div className="v" style={{ color: "var(--color-warn)" }}>{totalMissing.toLocaleString()}</div>
          <div className="d">need at least one asset</div>
        </div>
        <div className="s">
          <div className="k">STUDIOS</div>
          <div className="v">{STUDIOS.length}</div>
          <div className="d">FPVR · VRH · VRA · NJOI</div>
        </div>
      </div>

      {/* Per-studio strip */}
      <section className="ec-block" style={{ marginBottom: sceneSyncedAt ? 10 : 20 }}>
        <header>
          <h2>Production · by studio</h2>
          <div className="act"><span>{total.toLocaleString()} scenes total</span></div>
        </header>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${STUDIOS.length}, 1fr)`, padding: 0 }}>
          {STUDIOS.map((s, i) => {
            const count = stats.by_studio[s] ?? 0
            const abbr = studioAbbr(s)
            const color = studioColor(s)
            const isLast = i === STUDIOS.length - 1
            return (
              <div
                key={s}
                style={{
                  padding: "16px 18px",
                  borderRight: isLast ? undefined : "1px solid var(--color-border-subtle)",
                }}
              >
                <div style={{ fontSize: 10, letterSpacing: "0.18em", fontWeight: 400, color }}>{abbr}</div>
                <div style={{
                  fontSize: 28, fontWeight: 400, lineHeight: 1, marginTop: 4,
                  fontFamily: "var(--font-display-hero, var(--font-sans))",
                  letterSpacing: "-0.03em", color: "var(--color-text)",
                  fontVariantNumeric: "tabular-nums",
                }}>
                  {count.toLocaleString()}
                  <sup style={{ fontSize: 9, letterSpacing: "0.14em", color: "var(--color-text-muted)", marginLeft: 4, fontWeight: 400 }}>SCN</sup>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {sceneSyncedAt && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 20,
            padding: "6px 12px",
            fontSize: 10,
            color: "var(--color-text-faint)",
            letterSpacing: "0.06em",
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "var(--color-ok)",
              flexShrink: 0,
            }}
          />
          Catalog synced {relativeTime(sceneSyncedAt)}
        </div>
      )}
    </div>
  )
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

// ─── Briefing computation ───────────────────────────────────────────────────
//
// On /missing, the user is already past the "what do I work on" decision —
// they're here because they know. The briefing's job is to tell them which
// *specific* scene to start with: the earliest upcoming release still
// missing assets. Falls back to a count-focused variant if release dates
// aren't populated on the sampled scenes.

function computeMissingBriefing(input: {
  scenes: Scene[]
  totalMissing: number
  fetchFailed: boolean
}): Briefing {
  const { scenes, totalMissing, fetchFailed } = input

  if (fetchFailed) {
    return {
      eyebrow: "Next up",
      tone: "error",
      count: 0,
      headline: "Couldn't load scene catalog",
      detail: "The catalog is temporarily unreachable. Retry or open a specific scene via the filter tabs.",
      cta: null,
      secondary: [],
    }
  }

  const now = Date.now()
  const earliest = scenes
    .filter(s => parseLocalDate(s.release_date || "") !== null)
    .sort((a, b) => (a.release_date ?? "").localeCompare(b.release_date ?? ""))
    .find(s => {
      const gaps: string[] = []
      if (!s.has_description) gaps.push("description")
      if (!s.has_videos)      gaps.push("videos")
      if (!s.has_thumbnail)   gaps.push("thumbnail")
      if (!s.has_photos)      gaps.push("photos")
      if (!s.has_storyboard)  gaps.push("storyboard")
      return gaps.length > 0
    })

  if (earliest) {
    const gaps: string[] = []
    if (!earliest.has_description) gaps.push("description")
    if (!earliest.has_videos)      gaps.push("videos")
    if (!earliest.has_thumbnail)   gaps.push("thumbnail")
    if (!earliest.has_photos)      gaps.push("photos")
    if (!earliest.has_storyboard)  gaps.push("storyboard")
    const releaseDate = earliest.release_date ? earliest.release_date.slice(0, 10) : "TBD"
    const release = parseLocalDate(earliest.release_date || "")
    const daysOut = release !== null
      ? Math.round((release - now) / (24 * 60 * 60 * 1000))
      : null
    const when =
      daysOut === null ? "release date TBD" :
      daysOut < 0      ? `overdue by ${-daysOut}d` :
      daysOut === 0    ? "releases today" :
      daysOut === 1    ? "releases tomorrow" :
      `releases in ${daysOut}d`
    return {
      eyebrow: "Next up",
      tone: daysOut !== null && daysOut < 3 ? "urgent" : "attention",
      count: gaps.length,
      headline: `${earliest.id} — ${when}`,
      detail:
        `Earliest upcoming release still missing ${gaps.length === 1 ? "one asset" : `${gaps.length} assets`}` +
        ` (${gaps.join(", ")}). Start here to work through what's tightest on time.`,
      cta: { href: `/missing?scene=${encodeURIComponent(earliest.id)}`, label: "Open scene" },
      secondary: [
        `${totalMissing.toLocaleString()} scenes still missing assets`,
        `${releaseDate} · ${earliest.studio}`,
      ],
    }
  }

  // No release-date data available — fall back to a count variant.
  if (totalMissing > 0) {
    return {
      eyebrow: "Priority",
      tone: "attention",
      count: totalMissing,
      headline: `${totalMissing.toLocaleString()} scenes need validation`,
      detail: "Filter by studio or asset type below to triage. Scenes are grouped by studio so each lead can work their slice.",
      cta: null,
      secondary: [],
    }
  }

  return {
    eyebrow: "Next up",
    tone: "calm",
    count: 0,
    headline: "Catalog is clean",
    detail: "No scenes currently flagged as missing assets. Refresh MEGA below if a new shoot just landed.",
    cta: null,
    secondary: [],
  }
}
