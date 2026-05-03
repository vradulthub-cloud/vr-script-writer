"use client"

import { useCallback, useEffect, useRef, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ChevronRight, RotateCw } from "lucide-react"
import { type Scene, type Script } from "@/lib/api"
import { STUDIO_COLOR, STUDIO_ABBR } from "@/lib/studio-colors"
import { AssetCells, type AssetCell } from "@/components/ui/asset-cells"
import { SceneDetailModal } from "@/components/ui/scene-detail-modal"
import { triggerMegaRefresh, revalidateRecentActivity } from "./actions"

const ASSET_COLS = [
  { key: "has_description" as const, label: "Desc" },
  { key: "has_videos"      as const, label: "Videos" },
  { key: "has_thumbnail"   as const, label: "Thumb" },
  { key: "has_photos"      as const, label: "Photos" },
  { key: "has_storyboard"  as const, label: "Story" },
]

function sceneAssetCells(scene: Scene): AssetCell[] {
  return ASSET_COLS.map(a => ({
    label: a.label,
    status: scene[a.key] ? "ok" as const : "missing" as const,
  }))
}

// NJOI intentionally omitted from Recent activity — the team isn't actively
// triaging that studio's catalog on the dashboard. Surface it via /missing if
// needed.
const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure"]

interface Props {
  recentScenes: Scene[]
  missingTotal: number
  scripts: Script[]
  idToken?: string | undefined
  /** Server-side timestamp captured when this page was rendered. Drives the
   *  "updated Ns ago" indicator on the Refresh button. */
  generatedAt: number
}

// scan_mega.py takes ~50s to walk all four buckets; round up so we don't
// revalidate before the SQLite snapshot is rewritten.
const REFRESH_WAIT_MS = 60_000

export function TriageFeed({ recentScenes, scripts, idToken, generatedAt }: Props) {
  const router = useRouter()
  const [openScene, setOpenScene] = useState<Scene | null>(null)
  // Local cache of edits so optimistic updates from the modal show in
  // the dashboard list without requiring a re-fetch round-trip.
  const [overlayById, setOverlayById] = useState<Record<string, Scene>>({})
  const handleSceneUpdate = useCallback((updated: Scene) => {
    setOverlayById(prev => ({ ...prev, [updated.id]: updated }))
    setOpenScene(updated)
  }, [])

  // ─── Refresh state ─────────────────────────────────────────────────────
  const [isPending, startTransition] = useTransition()
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())

  // Tick once per second so the "updated Ns ago" label counts up live and
  // the in-flight countdown ticks down. Cheap — no network, no re-fetch.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const handleRefresh = useCallback(() => {
    setRefreshError(null)
    setSecondsLeft(Math.ceil(REFRESH_WAIT_MS / 1000))
    startTransition(async () => {
      const trigger = await triggerMegaRefresh()
      if (!trigger.ok) {
        setRefreshError(trigger.message)
        setSecondsLeft(null)
        return
      }
      // Tick the local countdown so the user sees progress while the
      // background scan runs on the server.
      const start = Date.now()
      await new Promise<void>(resolve => {
        const id = setInterval(() => {
          const remain = Math.max(0, REFRESH_WAIT_MS - (Date.now() - start))
          setSecondsLeft(Math.ceil(remain / 1000))
          if (remain <= 0) {
            clearInterval(id)
            resolve()
          }
        }, 1000)
      })
      await revalidateRecentActivity()
      router.refresh()
      setSecondsLeft(null)
    })
  }, [router])

  const ageSec = Math.max(0, Math.floor((now - generatedAt) / 1000))

  const merged = recentScenes.map(s => overlayById[s.id] ?? s)
  const byStudio = STUDIOS
    .map(s => ({
      studio: s,
      abbr: STUDIO_ABBR[s] ?? s,
      color: STUDIO_COLOR[s] ?? "var(--color-text-muted)",
      scenes: merged.filter(sc => sc.studio === s).slice(0, 5),
    }))
    .filter(g => g.scenes.length > 0)

  const hasAnything = byStudio.length > 0 || scripts.length > 0

  // j/k + ↑/↓ row navigation. Activates when focus is already inside the feed
  // so it doesn't hijack keys on unrelated pages. Enter activates via the
  // native button click — no explicit handler needed.
  const feedRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const root = feedRef.current
    if (!root) return
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (!["j", "k", "ArrowDown", "ArrowUp"].includes(e.key)) return
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return
      const rows = root!.querySelectorAll<HTMLButtonElement>("button[data-triage-row='true']")
      if (rows.length === 0) return
      const active = document.activeElement as HTMLElement | null
      const activeInFeed = active && root!.contains(active)
      const idx = activeInFeed ? Array.from(rows).indexOf(active as HTMLButtonElement) : -1
      let next = idx
      if (e.key === "j" || e.key === "ArrowDown") next = idx < 0 ? 0 : Math.min(rows.length - 1, idx + 1)
      if (e.key === "k" || e.key === "ArrowUp")   next = idx < 0 ? 0 : Math.max(0, idx - 1)
      if (next === idx && activeInFeed) return
      e.preventDefault()
      rows[next]?.focus()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [])

  const refreshLabel =
    secondsLeft !== null
      ? `Scanning S4… ${secondsLeft}s`
      : refreshError
      ? "Retry"
      : ageSec < 5
      ? "Refresh"
      : ageSec < 60
      ? `Refresh · ${ageSec}s ago`
      : `Refresh · ${Math.floor(ageSec / 60)}m ago`

  return (
    <div ref={feedRef}>
    <Section
      title="Recent activity"
      subtitle={hasAnything ? "Latest scenes per studio and scripts waiting on a writer. Use j/k or ↑/↓ to step through rows." : "No recent scenes found."}
      actions={
        <button
          type="button"
          onClick={handleRefresh}
          disabled={isPending}
          aria-label="Refresh from MEGA S4"
          title={refreshError ?? "Force a fresh MEGA S4 scan and rebuild the snapshot"}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "3px 8px",
            borderRadius: 3,
            fontSize: 11,
            fontVariantNumeric: "tabular-nums",
            background: "transparent",
            color: refreshError ? "var(--color-err)" : "var(--color-text-muted)",
            border: `1px solid ${refreshError ? "color-mix(in srgb, var(--color-err) 40%, transparent)" : "var(--color-border)"}`,
            cursor: isPending ? "wait" : "pointer",
            opacity: isPending ? 0.85 : 1,
            transition: "background-color 120ms",
          }}
          className="hover:bg-[--color-elevated]"
        >
          <RotateCw
            size={11}
            aria-hidden="true"
            style={{
              animation: isPending ? "spin 1s linear infinite" : undefined,
            }}
          />
          {refreshLabel}
        </button>
      }
    >
      {byStudio.map(group => (
        <div key={group.studio}>
          <div style={{
            padding: "7px 14px",
            display: "flex", alignItems: "baseline", gap: 8,
            borderBottom: "1px solid var(--color-border-subtle)",
            background: "var(--color-base)",
          }}>
            <Link
              href="/missing"
              style={{
                fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
                color: group.color, textDecoration: "none",
              }}
              className="hover:opacity-80"
            >
              {group.abbr}
            </Link>
            <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{group.studio}</span>
          </div>
          {group.scenes.map((scene, i) => {
            const cells = sceneAssetCells(scene)
            const dateStr = (scene.release_date ?? "").slice(0, 10)
            return (
              <button
                key={scene.id}
                type="button"
                onClick={() => setOpenScene(scene)}
                data-triage-row="true"
                style={{
                  padding: "8px 14px",
                  borderBottom: i < group.scenes.length - 1 ? "1px solid var(--color-border-subtle)" : "none",
                  display: "flex", alignItems: "center", gap: 10,
                  textDecoration: "none", color: "inherit",
                  width: "100%", textAlign: "left",
                  background: "transparent", border: "none",
                  cursor: "pointer",
                  font: "inherit",
                }}
                className="hover:bg-[--color-elevated]"
              >
                <span style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                  padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                  background: `color-mix(in srgb, ${group.color} 10%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${group.color} 28%, transparent)`,
                  color: group.color,
                }}>{group.abbr}</span>

                <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--color-text)", flexShrink: 0 }}>
                  {scene.id}
                </span>

                <span
                  title={scene.performers || undefined}
                  style={{
                    fontSize: 12, color: "var(--color-text)", fontWeight: 500,
                    flex: "1 1 auto", minWidth: 0,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}
                >
                  {scene.performers || <span style={{ color: "var(--color-text-faint)", fontStyle: "italic" }}>—</span>}
                </span>

                <span style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>
                  <AssetCells cells={cells} />
                </span>

                {dateStr && (
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                    {dateStr}
                  </span>
                )}
                <ChevronRight
                  size={12}
                  aria-hidden="true"
                  style={{
                    color: "var(--color-text-faint)",
                    opacity: 0.5,
                    flexShrink: 0,
                    marginLeft: -2,
                  }}
                />
              </button>
            )
          })}
        </div>
      ))}

      {scripts.length > 0 && (
        <div>
          <div style={{
            padding: "7px 14px",
            display: "flex", alignItems: "baseline", gap: 8,
            borderBottom: "1px solid var(--color-border-subtle)",
            borderTop: byStudio.length > 0 ? "1px solid var(--color-border)" : undefined,
            background: "var(--color-base)",
          }}>
            <Link
              href="/scripts"
              style={{
                fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
                color: "var(--color-text-muted)", textDecoration: "none",
              }}
              className="hover:text-[--color-text]"
            >
              Scripts Queued
            </Link>
            <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
              · {scripts.length}
            </span>
          </div>
          {scripts.slice(0, 5).map((script, i) => {
            const color = STUDIO_COLOR[script.studio] ?? "var(--color-text-muted)"
            const abbr = STUDIO_ABBR[script.studio] ?? script.studio
            const talent = [script.female, script.male].filter(Boolean).join(" / ")
            return (
              <div
                key={script.id}
                style={{
                  padding: "8px 14px",
                  borderBottom: i < Math.min(scripts.length, 5) - 1 ? "1px solid var(--color-border-subtle)" : "none",
                  display: "flex", alignItems: "center", gap: 10,
                }}
              >
                <span style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                  padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                  background: `color-mix(in srgb, ${color} 10%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${color} 28%, transparent)`,
                  color,
                }}>{abbr}</span>
                <span style={{ fontSize: 12, color: "var(--color-text)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {talent || "—"}
                </span>
                {script.shoot_date && (
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                    {script.shoot_date}
                  </span>
                )}
                <Link
                  href="/scripts"
                  style={{
                    padding: "3px 10px", borderRadius: 3, fontSize: 11, fontWeight: 500,
                    textDecoration: "none",
                    background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                    color: "var(--color-lime)",
                    border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                    flexShrink: 0,
                  }}
                >
                  Start
                </Link>
              </div>
            )
          })}
          {scripts.length > 5 && (
            <Link
              href="/scripts"
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                minHeight: 44, padding: "0 14px",
                fontSize: 11, color: "var(--color-text-muted)", textDecoration: "none",
              }}
              className="hover:bg-[--color-elevated]"
            >
              See all {scripts.length} →
            </Link>
          )}
        </div>
      )}
    </Section>
    <SceneDetailModal
      scene={openScene}
      idToken={idToken}
      onClose={() => setOpenScene(null)}
      onSceneUpdate={handleSceneUpdate}
    />
    </div>
  )
}

function Section({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  children: React.ReactNode
}) {
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
          alignItems: "flex-start",
          gap: 12,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2
            style={{
              margin: 0,
              fontSize: "0.8125rem",
              fontWeight: 600,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
              lineHeight: 1.2,
            }}
          >
            {title}
          </h2>
          {subtitle && (
            <p style={{ margin: "3px 0 0", fontSize: 12, color: "var(--color-text-faint)", lineHeight: 1.4, maxWidth: "65ch" }}>{subtitle}</p>
          )}
        </div>
        {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
      </div>
      {children}
    </div>
  )
}
