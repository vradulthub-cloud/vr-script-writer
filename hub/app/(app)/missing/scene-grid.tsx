"use client"

import { useState, useMemo, useCallback } from "react"
import { FilterTabs } from "@/components/ui/filter-tabs"
import { StudioBadge } from "@/components/ui/studio-badge"
import { ErrorAlert } from "@/components/ui/error-alert"
import { useIdToken } from "@/hooks/use-id-token"
import type { Scene, SceneStats } from "@/lib/api"
import { API_BASE_URL } from "@/lib/api"
import { SceneDetail } from "./scene-detail"

const STUDIOS = ["All", "FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

const ASSET_COLS = [
  { key: "has_description" as const, label: "Desc" },
  { key: "has_videos" as const,      label: "Videos" },
  { key: "has_thumbnail" as const,   label: "Thumb" },
  { key: "has_photos" as const,      label: "Photos" },
  { key: "has_storyboard" as const,  label: "Story" },
]

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

export function SceneGrid({ scenes: initialScenes, stats, error, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const [scenes, setScenes] = useState(initialScenes)
  const [studio, setStudio] = useState("All")
  const [missingOnly, setMissingOnly] = useState(false)
  const [search, setSearch] = useState("")
  const [megaRefreshing, setMegaRefreshing] = useState(false)
  const [megaMsg, setMegaMsg] = useState<string | null>(null)
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null)

  const handleSceneUpdate = useCallback((updated: Scene) => {
    setScenes((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
    setSelectedScene(updated)
  }, [])

  const studioCounts = useMemo(() => {
    const counts: Record<string, number> = { All: scenes.length }
    for (const s of STUDIOS.slice(1)) {
      counts[s] = scenes.filter(sc => sc.studio === s).length
    }
    return counts
  }, [scenes])

  const filtered = useMemo(() => {
    return scenes.filter(s => {
      if (studio !== "All" && s.studio !== studio) return false
      if (missingOnly) {
        const complete = ASSET_COLS.every(a => s[a.key])
        if (complete) return false
      }
      if (search) {
        const q = search.toLowerCase()
        return (
          s.title.toLowerCase().includes(q) ||
          s.performers.toLowerCase().includes(q) ||
          s.id.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [scenes, studio, missingOnly, search])

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

  // Detail view
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
      <div className="flex items-center gap-3 mb-4 flex-wrap">
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
          className="px-2.5 py-1 rounded text-xs transition-colors"
          style={{
            background: missingOnly ? "color-mix(in srgb, var(--color-warn) 15%, transparent)" : "transparent",
            color: missingOnly ? "var(--color-warn)" : "var(--color-text-muted)",
            border: `1px solid ${missingOnly ? "color-mix(in srgb, var(--color-warn) 30%, transparent)" : "var(--color-border)"}`,
          }}
        >
          Missing only
        </button>
        <input
          type="text"
          placeholder="Search title, performers, ID…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-[160px] max-w-xs px-2.5 py-1 rounded text-xs outline-none"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text)",
          }}
        />
        <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
          {filtered.length} scenes
        </span>
        <div className="flex items-center gap-2 ml-auto">
          {megaMsg && (
            <span style={{ fontSize: 11, color: megaMsg.includes("Scan") ? "var(--color-ok)" : "var(--color-err)" }}>
              {megaMsg}
            </span>
          )}
          <button
            onClick={triggerMegaRefresh}
            disabled={megaRefreshing}
            className="px-2.5 py-1 rounded text-xs transition-colors"
            style={{
              background: "transparent",
              color: megaRefreshing ? "var(--color-text-faint)" : "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: megaRefreshing ? "wait" : "pointer",
            }}
          >
            {megaRefreshing ? "Requesting…" : "Refresh MEGA"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <ErrorAlert className="p-4 text-sm mb-4">
          {error}
          <p className="mt-1 text-xs opacity-70">
            Could not reach the API. Check that the backend service is running.
          </p>
        </ErrorAlert>
      )}

      {/* Empty */}
      {!error && filtered.length === 0 && (
        <div
          className="rounded flex flex-col items-center justify-center gap-2"
          style={{
            height: 200,
            border: "1px dashed var(--color-border)",
            color: "var(--color-text-faint)",
          }}
        >
          <span style={{ fontSize: 24 }}>&#9673;</span>
          <span style={{ fontSize: 13 }}>
            {search ? `No scenes matching "${search}"` : missingOnly ? "All assets accounted for" : "No scenes loaded"}
          </span>
          {missingOnly && !search && (
            <span style={{ fontSize: 11, color: "var(--color-ok)" }}>Every scene has its assets. Nice.</span>
          )}
        </div>
      )}

      {/* Table */}
      {!error && filtered.length > 0 && (
        <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio</th>
                <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>ID</th>
                <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Title</th>
                <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Performers</th>
                {ASSET_COLS.map(col => (
                  <th key={col.key} className="text-center px-2 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {col.label}
                  </th>
                ))}
                <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Done</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((scene, i) => {
                const pct = completionPct(scene)
                return (
                  <tr
                    key={scene.id}
                    onClick={() => setSelectedScene(scene)}
                    data-complete={pct === 100 || undefined}
                    className="transition-colors cursor-pointer hover:bg-[--color-elevated]"
                    style={{
                      borderBottom: i < filtered.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
                    }}
                  >
                    <td className="px-3 py-1.5 whitespace-nowrap">
                      <StudioBadge studio={scene.studio} />
                    </td>
                    <td className="px-3 py-1.5 font-mono whitespace-nowrap" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                      {scene.id}
                    </td>
                    <td className="px-3 py-1.5" style={{ fontSize: 12, maxWidth: 280 }}>
                      <span className="line-clamp-1">{scene.title || <span style={{ color: "var(--color-text-faint)" }}>Untitled</span>}</span>
                    </td>
                    <td className="px-3 py-1.5" style={{ fontSize: 11, color: "var(--color-text-muted)", maxWidth: 180 }}>
                      <span className="line-clamp-1">{scene.performers || "—"}</span>
                    </td>
                    {ASSET_COLS.map(col => (
                      <td key={col.key} className="px-2 py-1.5 text-center">
                        <span
                          className="inline-flex items-center justify-center rounded-full"
                          style={{
                            width: 18,
                            height: 18,
                            fontSize: 10,
                            fontWeight: 600,
                            background: scene[col.key]
                              ? "color-mix(in srgb, var(--color-ok) 18%, transparent)"
                              : "color-mix(in srgb, var(--color-err) 12%, transparent)",
                            color: scene[col.key] ? "var(--color-ok)" : "var(--color-err)",
                          }}
                        >
                          {scene[col.key] ? "✓" : "✗"}
                        </span>
                      </td>
                    ))}
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1.5">
                        <div
                          className="rounded-full overflow-hidden"
                          style={{ width: 56, height: 5, background: "var(--color-border)" }}
                        >
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${pct}%`,
                              background: pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : "var(--color-err)",
                            }}
                          />
                        </div>
                        <span style={{
                          fontSize: 10,
                          fontWeight: 600,
                          minWidth: 28,
                          color: pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : pct > 0 ? "var(--color-err)" : "var(--color-text-faint)",
                        }}>
                          {pct}%
                        </span>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
