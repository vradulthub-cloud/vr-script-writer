"use client"

import { useState, useMemo, useCallback, useDeferredValue, useEffect, memo } from "react"
import { flushSync } from "react-dom"
import { useSearchParams } from "next/navigation"
import { RefreshCw, LayoutGrid, LayoutList, Wand2, Check, X as XIcon } from "lucide-react"
import { FilterTabs } from "@/components/ui/filter-tabs"
import { PageHeader } from "@/components/ui/page-header"
import { RetryError } from "@/components/ui/retry-error"
import { AssetCells, type AssetCell } from "@/components/ui/asset-cells"
import { GeneratedTitleModal } from "@/components/ui/generated-title-modal"
import { useIdToken } from "@/hooks/use-id-token"
import { api, type Scene, type SceneStats } from "@/lib/api"
import { API_BASE_URL } from "@/lib/api"
import { studioColor } from "@/lib/studio-colors"
import { completionPct } from "@/lib/scene-utils"
import { SceneDetail } from "./scene-detail"

/**
 * Wraps a state update in the View Transitions API so the browser captures
 * before/after DOM snapshots and morphs shared `view-transition-name`
 * elements between them. Falls back to an instant update in Firefox and
 * anywhere the API is absent.
 */
function morphTo(fn: () => void) {
  const doc = typeof document !== "undefined" ? document : null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const startViewTransition = (doc as any)?.startViewTransition
  if (!startViewTransition) {
    fn()
    return
  }
  startViewTransition.call(doc, () => flushSync(fn))
}

const STUDIOS = ["All", "FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]
const STUDIO_ORDER = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

// Studio colors flow from `lib/studio-colors` — single source of truth. Do
// NOT inline a local hex map here; any rebrand/a11y tweak should touch one
// file, not four.

const ASSET_COLS = [
  { key: "has_description" as const, label: "Desc" },
  { key: "has_videos"      as const, label: "Videos" },
  { key: "has_thumbnail"   as const, label: "Thumb" },
  { key: "has_photos"      as const, label: "Photos" },
  { key: "has_storyboard"  as const, label: "Story" },
]

function missingAssets(scene: Scene): string[] {
  return ASSET_COLS.filter(a => !scene[a.key]).map(a => a.label)
}

// completionPct lives in lib/scene-utils so scene-detail uses the
// same calculation. See ASSET_KEYS there for the canonical field list.

interface Props {
  scenes: Scene[]
  stats: SceneStats
  error: string | null
  idToken?: string | undefined
}

const PER_STUDIO_OPTIONS = [5, 10, 25, 50, 100] as const
type PerStudio = (typeof PER_STUDIO_OPTIONS)[number]

export function SceneGrid({ scenes: initialScenes, stats, error: initialError, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const [scenes, setScenes] = useState(initialScenes)
  const [studio, setStudio] = useState("All")
  const [missingOnly, setMissingOnly] = useState(true)
  const [search, setSearch] = useState("")
  const [megaRefreshing, setMegaRefreshing] = useState(false)
  const [megaMsg, setMegaMsg] = useState<string | null>(null)
  const [megaLastRefreshed, setMegaLastRefreshed] = useState<Date | null>(null)
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null)
  const [error, setError] = useState(initialError)
  const [perStudio, setPerStudio] = useState<PerStudio>(5)
  const [loadingMore, setLoadingMore] = useState(false)

  // Deep-link support: /missing?scene=VRH0762 opens the panel on that scene.
  // If the id isn't in the initial (paged) list, fetch it directly so a
  // bookmarked link doesn't silently open an empty page.
  const searchParams = useSearchParams()
  const [deepLinkError, setDeepLinkError] = useState<string | null>(null)
  useEffect(() => {
    const sceneId = searchParams?.get("scene")
    if (!sceneId) return
    const match = scenes.find(s => s.id === sceneId)
    if (match) {
      if (!selectedScene || selectedScene.id !== sceneId) setSelectedScene(match)
      return
    }
    // Not in the initial page — fetch it directly.
    let cancelled = false
    setDeepLinkError(null)
    api(idToken ?? null).scenes.get(sceneId).then((scene) => {
      if (cancelled) return
      setScenes(prev => prev.some(s => s.id === scene.id) ? prev : [scene, ...prev])
      setSelectedScene(scene)
    }).catch(() => {
      if (!cancelled) setDeepLinkError(sceneId)
    })
    return () => { cancelled = true }
    // scenes is intentionally omitted — only the URL param should drive this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, idToken])

  const handleSceneUpdate = useCallback((updated: Scene) => {
    setScenes(prev => prev.map(s => s.id === updated.id ? updated : s))
    setSelectedScene(updated)
  }, [])

  const studioCounts = useMemo(() => {
    const counts: Record<string, number> = { All: scenes.length }
    for (const s of STUDIOS.slice(1)) {
      counts[s] = scenes.filter(sc => sc.studio === s).length
    }
    return counts
  }, [scenes])

  // Deferred search lets the input stay snappy — typing updates the text
  // field immediately, but filtering/re-rendering runs at a lower priority.
  const deferredSearch = useDeferredValue(search)

  const byStudio = useMemo(() => {
    const q = deferredSearch ? deferredSearch.toLowerCase() : ""
    const groups: Record<string, Scene[]> = {}
    for (const scene of scenes) {
      if (studio !== "All" && scene.studio !== studio) continue
      if (missingOnly && ASSET_COLS.every(a => scene[a.key])) continue
      if (q) {
        if (
          !scene.title.toLowerCase().includes(q) &&
          !scene.performers.toLowerCase().includes(q) &&
          !scene.id.toLowerCase().includes(q)
        ) continue
      }
      if (!groups[scene.studio]) groups[scene.studio] = []
      groups[scene.studio].push(scene)
    }
    return groups
  }, [scenes, studio, missingOnly, deferredSearch])

  const totalVisible = Object.values(byStudio).reduce((n, arr) => n + arr.length, 0)

  async function reloadWithLimit(next: PerStudio) {
    setPerStudio(next)
    setLoadingMore(true)
    try {
      const client = api(idToken ?? null)
      const results = await Promise.all(
        STUDIO_ORDER.map(s =>
          client.scenes.list({ studio: s, limit: next, missing_only: missingOnly }),
        ),
      )
      setScenes(results.flat())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more scenes")
    } finally {
      setLoadingMore(false)
    }
  }

  async function triggerMegaRefresh() {
    setMegaRefreshing(true)
    setMegaMsg(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/scenes/mega-refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: "{}",
      })
      const data = await res.json()
      setMegaMsg(res.ok ? "Scan requested — results will sync in ~5 min" : (data.detail ?? "Request failed"))
      if (res.ok) setMegaLastRefreshed(new Date())
    } catch {
      setMegaMsg("Could not reach API")
    } finally {
      setMegaRefreshing(false)
    }
  }

  return (
    <div style={{ position: "relative" }}>
      {deepLinkError && (
        <div
          role="alert"
          className="rounded mb-3"
          style={{
            padding: "8px 12px",
            fontSize: 12,
            color: "var(--color-warn)",
            background: "color-mix(in srgb, var(--color-warn) 8%, transparent)",
            border: "1px solid color-mix(in srgb, var(--color-warn) 20%, transparent)",
          }}
        >
          Scene <span style={{ fontFamily: "var(--font-mono)" }}>{deepLinkError}</span> wasn&apos;t found in the current list and couldn&apos;t be fetched directly. It may have been renamed or removed.
        </div>
      )}
      <PageHeader
        title="Studio Catalog"
        eyebrow={`${totalVisible} shown · ${stats.missing_any} missing of ${stats.total}`}
        studioAccent={studio !== "All" ? studio : undefined}
        actions={
          <>
            <FilterTabs
              options={STUDIOS}
              value={studio}
              onChange={setStudio}
              counts={studioCounts}
            />
            {/* Divider separates studio filter (primary) from query controls (secondary) */}
            <span aria-hidden="true" style={{ width: 1, height: 16, background: "var(--color-border)", flexShrink: 0, alignSelf: "center" }} />
            <button
              role="switch"
              aria-checked={missingOnly}
              onClick={() => setMissingOnly(v => !v)}
              title={missingOnly
                ? "Showing only scenes missing at least one asset — click to show all"
                : "Showing all scenes — click to filter to only those missing assets"}
              style={{
                padding: "4px 10px", borderRadius: 4, fontSize: 11, cursor: "pointer",
                background: missingOnly ? "color-mix(in srgb, var(--color-warn) 15%, transparent)" : "transparent",
                color: missingOnly ? "var(--color-warn)" : "var(--color-text-muted)",
                border: `1px solid ${missingOnly ? "color-mix(in srgb, var(--color-warn) 30%, transparent)" : "var(--color-border)"}`,
              }}
            >
              Missing only
            </button>
            <input
              type="text"
              placeholder="Search…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                padding: "4px 10px", borderRadius: 4, fontSize: 11, outline: "none", minWidth: 140,
                background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)",
              }}
            />
            <label
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 11,
                color: "var(--color-text-muted)",
              }}
              title="Max scenes fetched per studio. Apply filters locally after."
            >
              Per studio
              <select
                value={perStudio}
                onChange={e => { void reloadWithLimit(Number(e.target.value) as PerStudio) }}
                disabled={loadingMore}
                style={{
                  padding: "3px 6px",
                  borderRadius: 4,
                  fontSize: 11,
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                  cursor: loadingMore ? "wait" : "pointer",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {PER_STUDIO_OPTIONS.map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
              {loadingMore && <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>loading…</span>}
            </label>
            {/* View toggle */}
            <div style={{ display: "flex", border: "1px solid var(--color-border)", borderRadius: 4, overflow: "hidden" }}>
              {(["grid", "list"] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  title={mode === "grid" ? "Grid view" : "List view"}
                  aria-label={mode === "grid" ? "Grid view" : "List view"}
                  aria-pressed={viewMode === mode}
                  style={{
                    padding: "4px 7px", cursor: "pointer",
                    background: viewMode === mode ? "var(--color-elevated)" : "transparent",
                    color: viewMode === mode ? "var(--color-text)" : "var(--color-text-faint)",
                    border: "none",
                  }}
                >
                  {mode === "grid" ? <LayoutGrid size={12} /> : <LayoutList size={12} />}
                </button>
              ))}
            </div>
            <button
              onClick={triggerMegaRefresh}
              disabled={megaRefreshing}
              title={
                megaRefreshing
                  ? "Scanning MEGA…"
                  : megaLastRefreshed
                  ? `Refresh MEGA — last requested ${megaLastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                  : "Refresh MEGA — scan for new files (~5 min)"
              }
              aria-label={megaRefreshing ? "Scanning MEGA" : "Refresh MEGA"}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 28, height: 28, borderRadius: 4, flexShrink: 0,
                cursor: megaRefreshing ? "wait" : "pointer",
                background: megaMsg && !megaMsg.includes("Scan") ? "color-mix(in srgb, var(--color-err) 10%, transparent)" : "transparent",
                border: `1px solid ${megaMsg && !megaMsg.includes("Scan") ? "color-mix(in srgb, var(--color-err) 25%, transparent)" : "var(--color-border)"}`,
                color: megaRefreshing ? "var(--color-text-faint)" : megaMsg && megaMsg.includes("Scan") ? "var(--color-ok)" : "var(--color-text-muted)",
              }}
            >
              <RefreshCw
                size={12}
                aria-hidden="true"
                style={{ animation: megaRefreshing ? "spin 0.8s linear infinite" : undefined }}
              />
            </button>
          </>
        }
      />

      {error && (
        <RetryError message={error} onRetry={() => { setError(null); window.location.reload() }} className="mb-4" />
      )}

      {/* Full-width grid; scene detail opens as a centered modal overlay. */}
      <div className="asset-tracker-shell">
        <div style={{ minWidth: 0 }}>
          {STUDIO_ORDER
            .filter(s => studio === "All" || s === studio)
            .map(studioName => {
              const studioScenes = byStudio[studioName] ?? []
              const color = studioColor(studioName)
              const isAllClear = studioScenes.length === 0
              return (
                <div key={studioName} style={{ marginBottom: 32 }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
                    <span style={{ fontWeight: 700, fontSize: 13, color }}>{studioName}</span>
                    {isAllClear
                      ? <span style={{ fontSize: 11, color: "var(--color-ok)" }}>all clear</span>
                      : <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{studioScenes.length} scene{studioScenes.length !== 1 ? "s" : ""} missing assets</span>
                    }
                  </div>

                  {isAllClear ? (
                    <AllClearCard color={color} />
                  ) : viewMode === "list" ? (
                    <div style={{ display: "flex", flexDirection: "column", borderRadius: 6, border: "1px solid var(--color-border)", overflow: "hidden" }}>
                      {studioScenes.map((scene, i) => (
                        <SceneRow
                          key={scene.id}
                          scene={scene}
                          selected={selectedScene?.id === scene.id}
                          isLast={i === studioScenes.length - 1}
                          onClick={() => morphTo(() => setSelectedScene(scene))}
                        />
                      ))}
                    </div>
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 8 }}>
                      {studioScenes.map(scene => (
                        <SceneCard
                          key={scene.id}
                          scene={scene}
                          selected={selectedScene?.id === scene.id}
                          onClick={() => morphTo(() => setSelectedScene(scene))}
                          idToken={idToken}
                          onSceneUpdate={handleSceneUpdate}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}

          {totalVisible === 0 && !error && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              height: 160, border: "1px dashed var(--color-border)", borderRadius: 6,
              color: "var(--color-text-faint)", fontSize: 13,
            }}>
              {missingOnly ? "All assets accounted for ✓" : "No scenes found"}
            </div>
          )}
        </div>

      </div>

      {/* Scene detail — centered modal overlay. Backdrop click + ESC close. */}
      <SceneDetailModal
        scene={selectedScene}
        idToken={idToken}
        onClose={() => morphTo(() => setSelectedScene(null))}
        onSceneUpdate={handleSceneUpdate}
      />
    </div>
  )
}

// ─── Scene detail modal: replaces the legacy sticky side panel ───────────────

function SceneDetailModal({
  scene,
  idToken,
  onClose,
  onSceneUpdate,
}: {
  scene: Scene | null
  idToken?: string
  onClose: () => void
  onSceneUpdate: (updated: Scene) => void
}) {
  // ESC closes the modal — matches the rest of the app's modal pattern
  // (compilations, generated-title, etc.).
  useEffect(() => {
    if (!scene) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [scene, onClose])

  // Lock body scroll while the modal is open so the backdrop doesn't
  // scroll the underlying grid when the user uses arrow keys / wheel.
  useEffect(() => {
    if (!scene) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = prev }
  }, [scene])

  if (!scene) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Scene ${scene.id} details`}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "min(5vh, 32px)",
        background: "color-mix(in srgb, var(--color-base) 70%, transparent)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
        animation: "scene-modal-fade 180ms ease-out",
      }}
    >
      <style jsx>{`
        @keyframes scene-modal-fade {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes scene-modal-rise {
          from { opacity: 0; transform: translateY(8px) scale(0.985); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(720px, 92vw)",
          maxWidth: 720,
          maxHeight: "calc(100vh - min(10vh, 64px))",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          boxShadow: "0 24px 60px -12px rgba(0,0,0,0.55), 0 8px 16px -8px rgba(0,0,0,0.4)",
          animation: "scene-modal-rise 220ms cubic-bezier(0.16, 1, 0.3, 1)",
          overflow: "hidden",
        }}
      >
        <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
          <SceneDetail
            key={scene.id}
            scene={scene}
            idToken={idToken}
            onClose={onClose}
            onSceneUpdate={onSceneUpdate}
          />
        </div>
      </div>
    </div>
  )
}

// ─── All-clear card: delightful empty state ──────────────────────────────────

function AllClearCard({ color }: { color: string }) {
  return (
    <div
      style={{
        padding: "14px 16px",
        borderRadius: 6,
        fontSize: 12,
        border: "1px solid color-mix(in srgb, var(--color-ok) 20%, transparent)",
        background: "color-mix(in srgb, var(--color-ok) 4%, transparent)",
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 20, height: 20,
          borderRadius: "50%",
          background: "color-mix(in srgb, var(--color-ok) 20%, transparent)",
          color: "var(--color-ok)",
          fontWeight: 700,
          fontSize: 12,
          flexShrink: 0,
        }}
      >
        ✓
      </span>
      <span style={{ color: "var(--color-text-muted)" }}>
        Every recent scene accounted for. <span style={{ color: "var(--color-text-faint)" }}>Nothing blocking.</span>
      </span>
      <span
        aria-hidden="true"
        style={{ marginLeft: "auto", width: 24, height: 2, background: color, opacity: 0.5, borderRadius: 1, flexShrink: 0 }}
      />
    </div>
  )
}

// React.memo prevents re-renders for unchanged scenes when filters or search
// state change elsewhere in the grid.
const SceneCard = memo(function SceneCard({
  scene, selected, onClick, idToken, onSceneUpdate,
}: {
  scene: Scene
  selected: boolean
  onClick: () => void
  idToken?: string
  onSceneUpdate: (updated: Scene) => void
}) {
  const missing = missingAssets(scene)
  const pct = completionPct(scene)
  const pctColor = pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : "var(--color-err)"
  const dateStr = (scene.release_date ?? "").slice(0, 10)
  const titleDisplay = scene.title
    ? (scene.title.length > 44 ? scene.title.slice(0, 44) + "…" : scene.title)
    : "—"

  const color = studioColor(scene.studio)

  const [genTitle, setGenTitle] = useState("")
  const [genBusy, setGenBusy] = useState<"idle" | "loading" | "saving">("idle")
  const [genErr, setGenErr] = useState<string | null>(null)
  const [genModalOpen, setGenModalOpen] = useState(false)

  async function runGenerate(e: React.MouseEvent | React.KeyboardEvent) {
    e.stopPropagation()
    setGenBusy("loading")
    setGenErr(null)
    try {
      const { title } = await api(idToken ?? null).scenes.generateTitle(scene.id, {
        female: scene.female,
        male: scene.male,
        theme: scene.theme,
        plot: scene.plot,
      })
      setGenTitle(title)
    } catch {
      setGenErr("Failed")
    } finally {
      setGenBusy("idle")
    }
  }

  async function runApply(e: React.MouseEvent) {
    e.stopPropagation()
    if (!genTitle) return
    setGenBusy("saving")
    try {
      await api(idToken ?? null).scenes.updateTitle(scene.id, genTitle)
      onSceneUpdate({ ...scene, title: genTitle })
      setGenTitle("")
    } catch {
      setGenErr("Save failed")
    } finally {
      setGenBusy("idle")
    }
  }

  function discard(e: React.MouseEvent) {
    e.stopPropagation()
    setGenTitle("")
    setGenErr(null)
  }

  // Unique view-transition-name tied to scene.id so the browser pairs
  // this card with the corresponding element in scene-detail.tsx when the
  // user clicks in or opens the panel. CSS-safe: scene IDs use [A-Z0-9-].
  const frameName = `scene-frame-${scene.id}`
  const codeName  = `scene-code-${scene.id}`

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick() } }}
      aria-pressed={selected}
      style={{
        background: selected
          ? `color-mix(in srgb, ${color} 10%, var(--color-elevated))`
          : "var(--color-surface)",
        border: selected
          ? `1px solid color-mix(in srgb, ${color} 45%, transparent)`
          : "1px solid var(--color-border)",
        borderRadius: 6,
        padding: "12px 14px",
        textAlign: "left",
        cursor: "pointer",
        width: "100%",
        viewTransitionName: frameName,
      }}
      onMouseEnter={e => {
        if (!selected) e.currentTarget.style.background = "var(--color-elevated)"
      }}
      onMouseLeave={e => {
        if (!selected) e.currentTarget.style.background = "var(--color-surface)"
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--color-text)", viewTransitionName: codeName }}>
          {scene.id}
        </span>
        {dateStr && <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{dateStr}</span>}
      </div>

      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginBottom: 2 }}>
        {scene.performers || "TBD"}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 10 }}>
        <span style={{ flex: 1, fontSize: 11, color: "var(--color-text-muted)", fontStyle: "italic", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {titleDisplay}
        </span>
        <button
          type="button"
          onClick={runGenerate}
          disabled={genBusy !== "idle"}
          aria-label="Generate title from script"
          title={genBusy === "loading" ? "Generating…" : "Generate title from script"}
          style={{
            flexShrink: 0,
            width: 20,
            height: 20,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 3,
            background: "transparent",
            color: genBusy === "loading" ? "var(--color-text-faint)" : color,
            border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
            cursor: genBusy === "loading" ? "wait" : "pointer",
            padding: 0,
          }}
        >
          <Wand2 size={11} aria-hidden="true" />
        </button>
      </div>

      {(genTitle || genErr) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginBottom: 8,
            padding: "4px 6px",
            borderRadius: 3,
            background: "var(--color-elevated)",
            border: `1px solid color-mix(in srgb, ${color} 25%, var(--color-border))`,
          }}
        >
          {genErr ? (
            <>
              <span style={{ flex: 1, fontSize: 10, color: "var(--color-err)" }}>{genErr}</span>
              <button
                type="button"
                onClick={discard}
                aria-label="Dismiss"
                style={{
                  width: 16, height: 16, padding: 0,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  background: "transparent", color: "var(--color-text-faint)",
                  border: "none", cursor: "pointer",
                }}
              >
                <XIcon size={10} aria-hidden="true" />
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={e => { e.stopPropagation(); setGenModalOpen(true) }}
                title="Preview in context"
                style={{
                  flex: 1,
                  minWidth: 0,
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--color-text)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  background: "transparent",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                }}
              >
                {genTitle}
              </button>
              <button
                type="button"
                onClick={runApply}
                disabled={genBusy === "saving"}
                aria-label="Apply generated title"
                title="Apply"
                style={{
                  width: 18, height: 18, padding: 0,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  borderRadius: 3, background: "var(--color-lime)", color: "var(--color-lime-ink)",
                  border: "none", cursor: genBusy === "saving" ? "wait" : "pointer",
                }}
              >
                <Check size={11} aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={discard}
                aria-label="Discard"
                title="Discard"
                style={{
                  width: 18, height: 18, padding: 0,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  borderRadius: 3, background: "transparent", color: "var(--color-text-faint)",
                  border: "1px solid var(--color-border)", cursor: "pointer",
                }}
              >
                <XIcon size={11} aria-hidden="true" />
              </button>
            </>
          )}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 7 }}>
        <div style={{ flex: 1, height: 3, background: "var(--color-border)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: pctColor, borderRadius: 2 }} />
        </div>
        <span style={{ fontSize: 10, fontWeight: 600, color: pctColor }}>{pct}%</span>
      </div>

      <AssetCells
        cells={ASSET_COLS.map<AssetCell>(a => ({
          label: a.label,
          status: scene[a.key] ? "ok" : "missing",
        }))}
      />

      {genModalOpen && genTitle && (
        <GeneratedTitleModal
          scene={scene}
          title={genTitle}
          busy={genBusy}
          error={genErr}
          onApply={async () => {
            await runApply({ stopPropagation: () => {} } as unknown as React.MouseEvent)
            setGenModalOpen(false)
          }}
          onRegenerate={() => runGenerate({ stopPropagation: () => {} } as unknown as React.MouseEvent)}
          onDiscard={() => { setGenTitle(""); setGenErr(null); setGenModalOpen(false) }}
          onClose={() => setGenModalOpen(false)}
        />
      )}
    </div>
  )
})

// Dense single-row rendering used when the side panel is open. Shows
// everything a card shows, horizontally, in ~36px of vertical space.
const SceneRow = memo(function SceneRow({
  scene, selected, isLast, onClick,
}: { scene: Scene; selected: boolean; isLast: boolean; onClick: () => void }) {
  const missing = missingAssets(scene)
  const pct = completionPct(scene)
  const pctColor = pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : "var(--color-err)"
  const color = studioColor(scene.studio)

  const frameName = `scene-frame-${scene.id}`
  const codeName  = `scene-code-${scene.id}`

  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        width: "100%",
        padding: "8px 12px",
        background: selected
          ? `color-mix(in srgb, ${color} 10%, var(--color-elevated))`
          : "var(--color-surface)",
        border: "none",
        borderBottom: isLast ? undefined : "1px solid var(--color-border-subtle)",
        cursor: "pointer",
        textAlign: "left",
        viewTransitionName: frameName,
      }}
      onMouseEnter={e => {
        if (!selected) e.currentTarget.style.background = "var(--color-elevated)"
      }}
      onMouseLeave={e => {
        if (!selected) e.currentTarget.style.background = "var(--color-surface)"
      }}
    >
      <span
        className="font-mono"
        style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text)", minWidth: 70, viewTransitionName: codeName }}
      >
        {scene.id}
      </span>

      <span style={{ fontSize: 11, color: "var(--color-text-muted)", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {scene.performers || "TBD"}
      </span>

      <div style={{ display: "flex", gap: 2, flexShrink: 0 }}>
        {missing.length === 0
          ? <span style={{ fontSize: 10, color: "var(--color-ok)", fontWeight: 600 }}>✓</span>
          : missing.map(m => (
              <span key={m} style={{
                fontSize: 9, fontWeight: 600, padding: "0 4px", borderRadius: 2,
                background: "color-mix(in srgb, var(--color-err) 12%, transparent)",
                color: "var(--color-err)",
              }}>
                {m}
              </span>
            ))
        }
      </div>

      <span style={{
        fontSize: 10, fontWeight: 700, color: pctColor,
        fontVariantNumeric: "tabular-nums",
        minWidth: 32, textAlign: "right", flexShrink: 0,
      }}>
        {pct}%
      </span>
    </button>
  )
})
