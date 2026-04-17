"use client"

import { useState, useMemo, useCallback } from "react"
import { FilterTabs } from "@/components/ui/filter-tabs"
import { RetryError } from "@/components/ui/retry-error"
import { useIdToken } from "@/hooks/use-id-token"
import type { Scene, SceneStats } from "@/lib/api"
import { API_BASE_URL } from "@/lib/api"
import { SceneDetail } from "./scene-detail"

const STUDIOS = ["All", "FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]
const STUDIO_ORDER = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

const STUDIO_COLOR: Record<string, string> = {
  "FuckPassVR": "#3b82f6",
  "VRHush":     "#8b5cf6",
  "VRAllure":   "#ec4899",
  "NaughtyJOI": "#f97316",
}

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

function completionPct(scene: Scene): number {
  const present = ASSET_COLS.filter(a => scene[a.key]).length
  return Math.round((present / ASSET_COLS.length) * 100)
}

interface Props {
  scenes: Scene[]
  stats: SceneStats
  error: string | null
  idToken?: string | undefined
}

export function SceneGrid({ scenes: initialScenes, stats, error: initialError, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const [scenes, setScenes] = useState(initialScenes)
  const [studio, setStudio] = useState("All")
  const [missingOnly, setMissingOnly] = useState(true)
  const [search, setSearch] = useState("")
  const [megaRefreshing, setMegaRefreshing] = useState(false)
  const [megaMsg, setMegaMsg] = useState<string | null>(null)
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null)
  const [error, setError] = useState(initialError)

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

  const byStudio = useMemo(() => {
    const groups: Record<string, Scene[]> = {}
    for (const scene of scenes) {
      if (studio !== "All" && scene.studio !== studio) continue
      if (missingOnly && ASSET_COLS.every(a => scene[a.key])) continue
      if (search) {
        const q = search.toLowerCase()
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
  }, [scenes, studio, missingOnly, search])

  const totalVisible = Object.values(byStudio).reduce((n, arr) => n + arr.length, 0)

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
    } catch {
      setMegaMsg("Could not reach API")
    } finally {
      setMegaRefreshing(false)
    }
  }

  if (selectedScene) {
    return (
      <SceneDetail
        scene={selectedScene}
        idToken={idToken}
        onBack={() => setSelectedScene(null)}
        onSceneUpdate={handleSceneUpdate}
      />
    )
  }

  return (
    <div>
      {/* Filter bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24, flexWrap: "wrap" }}>
        <FilterTabs
          options={STUDIOS}
          value={studio}
          onChange={setStudio}
          counts={studioCounts}
        />
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
        <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{totalVisible}</span> shown ·{" "}
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{stats.missing_any}</span> missing of{" "}
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{stats.total}</span>
        </span>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          {megaMsg && (
            <span style={{ fontSize: 11, color: megaMsg.includes("Scan") ? "var(--color-ok)" : "var(--color-err)" }}>
              {megaMsg}
            </span>
          )}
          <button
            onClick={triggerMegaRefresh}
            disabled={megaRefreshing}
            title="Scan MEGA for new files — results will sync in ~5 minutes"
            style={{
              padding: "4px 10px", borderRadius: 4, fontSize: 11, cursor: megaRefreshing ? "wait" : "pointer",
              background: "transparent", border: "1px solid var(--color-border)",
              color: megaRefreshing ? "var(--color-text-faint)" : "var(--color-text-muted)",
            }}
          >
            {megaRefreshing ? "Requesting…" : "Refresh MEGA"}
          </button>
        </div>
      </div>

      {error && (
        <RetryError message={error} onRetry={() => { setError(null); window.location.reload() }} className="mb-4" />
      )}

      {/* Studio sections */}
      {STUDIO_ORDER
        .filter(s => studio === "All" || s === studio)
        .map(studioName => {
          const studioScenes = byStudio[studioName] ?? []
          const color = STUDIO_COLOR[studioName] ?? "var(--color-border)"
          return (
            <div key={studioName} style={{ marginBottom: 32 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <div style={{ width: 3, height: 18, borderRadius: 2, background: color, flexShrink: 0 }} />
                <span style={{ fontWeight: 700, fontSize: 13, color: "var(--color-text)" }}>{studioName}</span>
                {studioScenes.length === 0
                  ? <span style={{ fontSize: 11, color: "var(--color-ok)" }}>all clear</span>
                  : <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{studioScenes.length} scene{studioScenes.length !== 1 ? "s" : ""} missing assets</span>
                }
              </div>

              {studioScenes.length === 0 ? (
                <div style={{
                  padding: "10px 14px", borderRadius: 6, fontSize: 12,
                  border: "1px dashed var(--color-border)", color: "var(--color-text-faint)",
                }}>
                  No missing assets in recent scenes.
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 8 }}>
                  {studioScenes.map(scene => (
                    <SceneCard key={scene.id} scene={scene} onClick={() => setSelectedScene(scene)} />
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
  )
}

function SceneCard({ scene, onClick }: { scene: Scene; onClick: () => void }) {
  const missing = missingAssets(scene)
  const pct = completionPct(scene)
  const pctColor = pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : "var(--color-err)"
  const dateStr = (scene.release_date ?? "").slice(0, 10)
  const titleDisplay = scene.title
    ? (scene.title.length > 44 ? scene.title.slice(0, 44) + "…" : scene.title)
    : "—"

  return (
    <button
      onClick={onClick}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        padding: "12px 14px",
        textAlign: "left",
        cursor: "pointer",
        width: "100%",
      }}
      onMouseEnter={e => (e.currentTarget.style.background = "var(--color-elevated)")}
      onMouseLeave={e => (e.currentTarget.style.background = "var(--color-surface)")}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
        <span style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 700, color: "var(--color-text)" }}>
          {scene.id}
        </span>
        {dateStr && <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{dateStr}</span>}
      </div>

      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginBottom: 2 }}>
        {scene.performers || "TBD"}
      </div>

      <div style={{ fontSize: 11, color: "var(--color-text-muted)", fontStyle: "italic", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginBottom: 10 }}>
        {titleDisplay}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 7 }}>
        <div style={{ flex: 1, height: 3, background: "var(--color-border)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: pctColor, borderRadius: 2 }} />
        </div>
        <span style={{ fontSize: 10, fontWeight: 600, color: pctColor }}>{pct}%</span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
        {missing.length === 0
          ? <span style={{ fontSize: 10, color: "var(--color-ok)" }}>✓ complete</span>
          : missing.map(m => (
              <span key={m} style={{
                fontSize: 10, fontWeight: 600, padding: "1px 5px", borderRadius: 3,
                background: "color-mix(in srgb, var(--color-err) 12%, transparent)",
                color: "var(--color-err)",
              }}>
                {m}
              </span>
            ))
        }
      </div>
    </button>
  )
}
