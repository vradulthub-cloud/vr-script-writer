"use client"

import { useState, useMemo, useCallback, useRef, useEffect } from "react"
import { FilterTabs } from "@/components/ui/filter-tabs"
import { StudioBadge } from "@/components/ui/studio-badge"
import { RetryError } from "@/components/ui/retry-error"
import { useIdToken } from "@/hooks/use-id-token"
import type { Scene, SceneStats } from "@/lib/api"
import { API_BASE_URL } from "@/lib/api"
import { SceneDetail } from "./scene-detail"
import { ChevronUp, ChevronDown } from "lucide-react"

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

type SortKey = "studio" | "id" | "title" | "performers" | "completion"
type SortDir = "asc" | "desc"

const ROW_HEIGHT = 44
const OVERSCAN = 8

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
  // Missing tab defaults to showing only what's missing — matches the old Streamlit UX
  const [missingOnly, setMissingOnly] = useState(true)
  const [search, setSearch] = useState("")
  const [megaRefreshing, setMegaRefreshing] = useState(false)
  const [megaMsg, setMegaMsg] = useState<string | null>(null)
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null)
  const [error, setError] = useState(initialError)

  // Sort state
  const [sortKey, setSortKey] = useState<SortKey>("completion")
  const [sortDir, setSortDir] = useState<SortDir>("asc")

  // Virtual scroll refs
  const containerRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(600)

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
    let result = scenes.filter(s => {
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

    // Sort
    result = [...result].sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case "studio":     cmp = a.studio.localeCompare(b.studio); break
        case "id":         cmp = a.id.localeCompare(b.id); break
        case "title":      cmp = (a.title || "").localeCompare(b.title || ""); break
        case "performers": cmp = (a.performers || "").localeCompare(b.performers || ""); break
        case "completion":  cmp = completionPct(a) - completionPct(b); break
      }
      return sortDir === "asc" ? cmp : -cmp
    })

    return result
  }, [scenes, studio, missingOnly, search, sortKey, sortDir])

  // Virtual scroll calculation
  const totalHeight = filtered.length * ROW_HEIGHT
  const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN)
  const endIdx = Math.min(filtered.length, Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + OVERSCAN)
  const visibleRows = filtered.slice(startIdx, endIdx)
  const offsetY = startIdx * ROW_HEIGHT

  // Measure container
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height)
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir(key === "completion" ? "asc" : "asc")
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return null
    return sortDir === "asc"
      ? <ChevronUp size={10} style={{ marginLeft: 2, opacity: 0.7 }} />
      : <ChevronDown size={10} style={{ marginLeft: 2, opacity: 0.7 }} />
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
      <div className="flex items-center gap-3 mb-5 flex-wrap">
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
        <RetryError
          message={error}
          onRetry={() => {
            setError(null)
            window.location.reload()
          }}
          className="mb-4"
        />
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
          <span style={{ fontSize: 13 }}>
            {search ? `No scenes matching "${search}"` : missingOnly ? "All assets accounted for" : "No scenes loaded"}
          </span>
          {missingOnly && !search && (
            <span style={{ fontSize: 11, color: "var(--color-ok)" }}>Every scene has its assets.</span>
          )}
        </div>
      )}

      {/* Table with virtual scroll */}
      {!error && filtered.length > 0 && (
        <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                <th
                  className="text-left px-3 py-2 font-medium cursor-pointer select-none"
                  style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  onClick={() => handleSort("studio")}
                >
                  <span className="inline-flex items-center">Studio<SortIcon col="studio" /></span>
                </th>
                <th
                  className="text-left px-3 py-2 font-medium cursor-pointer select-none"
                  style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  onClick={() => handleSort("id")}
                >
                  <span className="inline-flex items-center">ID<SortIcon col="id" /></span>
                </th>
                <th className="px-2 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)", width: 56 }}>
                  Preview
                </th>
                <th
                  className="text-left px-3 py-2 font-medium cursor-pointer select-none"
                  style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  onClick={() => handleSort("title")}
                >
                  <span className="inline-flex items-center">Title<SortIcon col="title" /></span>
                </th>
                <th
                  className="text-left px-3 py-2 font-medium cursor-pointer select-none"
                  style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  onClick={() => handleSort("performers")}
                >
                  <span className="inline-flex items-center">Performers<SortIcon col="performers" /></span>
                </th>
                {ASSET_COLS.map(col => (
                  <th key={col.key} className="text-center px-2 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {col.label}
                  </th>
                ))}
                <th
                  className="text-left px-3 py-2 font-medium cursor-pointer select-none"
                  style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  onClick={() => handleSort("completion")}
                >
                  <span className="inline-flex items-center">Done<SortIcon col="completion" /></span>
                </th>
              </tr>
            </thead>
          </table>

          {/* Virtual scroll body */}
          <div
            ref={containerRef}
            className="overflow-y-auto"
            style={{ maxHeight: "calc(100vh - 280px)" }}
            onScroll={(e) => setScrollTop((e.target as HTMLElement).scrollTop)}
          >
            <div style={{ height: totalHeight, position: "relative" }}>
              <table className="w-full" style={{ borderCollapse: "collapse", position: "absolute", top: offsetY, left: 0, right: 0 }}>
                <tbody>
                  {visibleRows.map((scene, i) => {
                    const pct = completionPct(scene)
                    const rowIdx = startIdx + i
                    return (
                      <tr
                        key={scene.id}
                        onClick={() => setSelectedScene(scene)}
                        data-complete={pct === 100 || undefined}
                        className="transition-colors cursor-pointer hover:bg-[--color-elevated]"
                        style={{
                          height: ROW_HEIGHT,
                          borderBottom: rowIdx < filtered.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
                        }}
                      >
                        <td className="px-3 py-1.5 whitespace-nowrap">
                          <StudioBadge studio={scene.studio} />
                        </td>
                        <td className="px-3 py-1.5 font-mono whitespace-nowrap" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                          {scene.id}
                        </td>
                        <td className="px-2 py-1" style={{ width: 56 }}>
                          <ThumbCell scene={scene} />
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
                                className="h-full rounded-full"
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
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function ThumbCell({ scene }: { scene: Scene }) {
  const [failed, setFailed] = useState(false)

  if (!scene.has_thumbnail || failed) {
    return (
      <div
        className="rounded"
        style={{
          width: 48, height: 32,
          background: "var(--color-elevated)",
          border: "1px dashed var(--color-border)",
        }}
      />
    )
  }

  return (
    <img
      src={`${API_BASE_URL}/api/scenes/${encodeURIComponent(scene.id)}/thumbnail`}
      alt=""
      aria-hidden="true"
      loading="lazy"
      onError={() => setFailed(true)}
      className="rounded"
      style={{
        width: 48, height: 32,
        objectFit: "cover",
        background: "var(--color-elevated)",
        display: "block",
      }}
    />
  )
}

function MetricCard({ label, value, accent, context }: {
  label: string
  value: number
  accent?: "ok" | "warn" | "muted"
  context?: string
}) {
  const valueColor =
    accent === "ok"   ? "var(--color-ok)"   :
    accent === "warn" ? "var(--color-warn)" :
    accent === "muted" ? "var(--color-text-muted)" :
    "var(--color-text)"

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        padding: "10px 14px",
      }}
    >
      <div
        style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.07em",
          textTransform: "uppercase", color: "var(--color-text-faint)",
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-2 mt-1">
        <span
          style={{
            fontSize: 24, fontWeight: 700, lineHeight: 1,
            color: valueColor,
            letterSpacing: "-0.02em",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {value.toLocaleString()}
        </span>
        {context && (
          <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
            {context}
          </span>
        )}
      </div>
    </div>
  )
}
