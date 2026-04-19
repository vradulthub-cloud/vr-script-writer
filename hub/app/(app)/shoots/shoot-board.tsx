"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { CheckCircle2, AlertTriangle, Circle, Clock, X, RefreshCcw, Film } from "lucide-react"
import {
  api,
  type Shoot,
  type BoardShootScene,
  type SceneAssetState,
  type AssetStatus,
  type AssetType,
  SHOOT_ASSET_ORDER,
  SHOOT_ASSET_LABELS,
} from "@/lib/api"
import { studioColor } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { formatApiError } from "@/lib/errors"

// ── Config ────────────────────────────────────────────────────────────
const POLL_MS = 30_000
const AGING_WARN_HOURS = 48       // >48h post-shoot with gaps → red accent
const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const

// ── Status helpers ────────────────────────────────────────────────────
function statusColor(status: AssetStatus, hasValidityWarning: boolean): string {
  if (status === "stuck") return "var(--color-err)"
  if (status === "validated") return hasValidityWarning ? "var(--color-warn)" : "var(--color-ok)"
  if (status === "available") return "var(--color-warn)"
  return "var(--color-border)"
}

const STATUS_LABEL: Record<AssetStatus, string> = {
  not_present: "not yet",
  available:   "in flight",
  validated:   "validated",
  stuck:       "stuck",
}

// ── Phase grouping ────────────────────────────────────────────────────
// The 11 asset cells split into three pipeline phases. We render an extra
// gap between phases so users can tell at a glance which cell is which.
const PHASES: { name: string; assets: AssetType[] }[] = [
  { name: "Plan",  assets: ["script_done", "call_sheet_sent", "legal_run", "grail_run"] },
  { name: "Shoot", assets: ["bg_edit_uploaded", "solo_uploaded"] },
  { name: "Post",  assets: ["title_done", "encoded_uploaded", "photoset_uploaded", "storyboard_uploaded", "legal_docs_uploaded"] },
]
const PHASE_GAP = 10  // px between phase clusters
const CELL_GAP  = 2   // px between cells inside a phase

// Which asset cells actually apply to a given scene_type. Cells that don't
// apply (e.g. "BG edit" on a Solo scene) are dimmed in the strip and hidden
// in the detail table so the UI doesn't mislead with false negatives.
function cellApplies(assetType: AssetType, sceneType: string): boolean {
  const t = (sceneType || "").toUpperCase()
  const isSolo = t === "SOLO" || t === "JOI"
  const isBG   = t === "BG"   || t === "BGCP"
  switch (assetType) {
    case "bg_edit_uploaded":     return isBG
    case "solo_uploaded":        return isSolo
    case "legal_run":            return isBG
    case "legal_docs_uploaded":  return isBG
    // call_sheet_sent, grail_run, script_done, title_done, encoded_uploaded,
    // photoset_uploaded, storyboard_uploaded apply to every scene type
    default: return true
  }
}

function statusIcon(status: AssetStatus, hasValidityWarning: boolean) {
  if (status === "stuck")     return <AlertTriangle size={10} aria-hidden="true" />
  if (status === "validated") return hasValidityWarning ? <AlertTriangle size={10} aria-hidden="true" /> : <CheckCircle2 size={10} aria-hidden="true" />
  if (status === "available") return <Clock size={10} aria-hidden="true" />
  return <Circle size={10} aria-hidden="true" strokeWidth={1.5} />
}

function shootCompleteness(shoot: Shoot): { validated: number; total: number } {
  let validated = 0
  let total = 0
  for (const s of shoot.scenes) {
    for (const a of s.assets) {
      total += 1
      if (a.status === "validated") validated += 1
    }
  }
  return { validated, total }
}

function isAlert(shoot: Shoot): boolean {
  if (shoot.aging_hours < AGING_WARN_HOURS) return false
  const { validated, total } = shootCompleteness(shoot)
  return total > 0 && validated < total
}

function formatShootDate(iso: string): string {
  if (!iso) return ""
  try {
    const d = new Date(iso + "T00:00:00")
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", weekday: "short" })
  } catch {
    return iso
  }
}

function relativeFromHours(hours: number): string {
  if (hours === 0) return "upcoming / today"
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// ── Props ─────────────────────────────────────────────────────────────
interface Props {
  initialShoots: Shoot[]
  error: string | null
  idToken: string | undefined
}

export function ShootBoard({ initialShoots, error: initialError, idToken: serverToken }: Props) {
  const idToken = useIdToken(serverToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [shoots, setShoots] = useState<Shoot[]>(initialShoots)
  const [error, setError] = useState<string | null>(initialError)
  const [studioFilter, setStudioFilter] = useState<string>("All")
  // Month filter key: "" = default window (current + next month), or a
  // specific month in YYYY-MM form for a custom 1-month view.
  const [monthFilter, setMonthFilter] = useState<string>("")
  const [selectedShootId, setSelectedShootId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshFailures, setRefreshFailures] = useState(0)
  const [popoverCell, setPopoverCell] = useState<{
    shootId: string
    position: number
    assetType: AssetType
  } | null>(null)
  const inFlightRef = useRef<Set<string>>(new Set())

  const selected = useMemo(
    () => shoots.find(s => s.shoot_id === selectedShootId) ?? null,
    [shoots, selectedShootId],
  )

  const refresh = useCallback(async () => {
    if (!idToken) return
    setRefreshing(true)
    try {
      const filters: { from_date?: string; to_date?: string } = {}
      if (monthFilter) {
        // YYYY-MM → full calendar month window
        const [y, m] = monthFilter.split("-").map(Number)
        const first = new Date(y, m - 1, 1)
        const last  = new Date(y, m, 0)  // day 0 of next month = last of this
        const pad = (n: number) => String(n).padStart(2, "0")
        filters.from_date = `${y}-${pad(m)}-${pad(first.getDate())}`
        filters.to_date   = `${y}-${pad(m)}-${pad(last.getDate())}`
      }
      const next = await client.shoots.list(filters)
      setShoots(next)
      setError(null)
      setRefreshFailures(0)
    } catch (e) {
      setRefreshFailures(n => n + 1)
      // Only surface the error banner after 2 consecutive failures so a
      // transient blip doesn't nag the user.
      if (refreshFailures >= 1) {
        setError(formatApiError(e, "Refresh"))
      }
    } finally {
      setRefreshing(false)
    }
  }, [client, idToken, monthFilter, refreshFailures])

  // Re-fetch when the month filter changes
  useEffect(() => { void refresh() }, [monthFilter])  // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(() => { void refresh() }, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  const filtered = useMemo(() => {
    if (studioFilter === "All") return shoots
    return shoots.filter(s => s.scenes.some(sc => sc.studio === studioFilter))
  }, [shoots, studioFilter])

  const counts = useMemo(() => {
    const c: Record<string, number> = { All: shoots.length }
    for (const st of STUDIOS) {
      c[st] = shoots.filter(s => s.scenes.some(sc => sc.studio === st)).length
    }
    return c
  }, [shoots])

  return (
    <div>
      {/* Header / filter bar */}
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div
          className="flex items-center gap-1 rounded-md"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", padding: "3px" }}
        >
          {(["All", ...STUDIOS] as const).map(st => {
            const active = studioFilter === st
            const color = st === "All" ? "var(--color-lime)" : studioColor(st)
            return (
              <button
                key={st}
                onClick={() => setStudioFilter(st)}
                aria-pressed={active}
                className="rounded px-2 py-1 transition-colors"
                style={{
                  fontSize: 11,
                  fontWeight: active ? 600 : 400,
                  background: active ? "var(--color-elevated)" : "transparent",
                  color: active ? color : "var(--color-text-muted)",
                  border: "none",
                }}
              >
                {st} <span className="tabular-nums" style={{ opacity: 0.7 }}>{counts[st] ?? 0}</span>
              </button>
            )
          })}
        </div>
        <div className="flex items-center gap-2">
          <MonthFilter value={monthFilter} onChange={setMonthFilter} />
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
            {refreshing ? "Refreshing…" : "Auto-refreshes every 30s"}
          </span>
          <button
            onClick={() => { void refresh() }}
            disabled={refreshing}
            className="px-2.5 py-1 rounded text-xs transition-colors"
            style={{
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: refreshing ? "not-allowed" : "pointer",
              opacity: refreshing ? 0.5 : 1,
            }}
          >
            <RefreshCcw size={11} className="inline mr-1" aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>

      {error && <ErrorAlert className="mb-3">{error}</ErrorAlert>}

      {filtered.length === 0 && !error ? (
        <EmptyState filter={studioFilter} />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: selected ? "minmax(0, 1fr) 480px" : "minmax(0, 1fr) 0px",
            columnGap: selected ? 12 : 0,
            alignItems: "flex-start",
            transition: "grid-template-columns 220ms cubic-bezier(0.16, 1, 0.3, 1), column-gap 220ms",
          }}
        >
          <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            <AssetLegend />
            {filtered.map(shoot => (
              <ShootRow
                key={shoot.shoot_id}
                shoot={shoot}
                selected={shoot.shoot_id === selectedShootId}
                onSelect={() => setSelectedShootId(shoot.shoot_id)}
                onCellClick={(sceneIdx, assetType) =>
                  setPopoverCell({
                    shootId: shoot.shoot_id,
                    position: shoot.scenes[sceneIdx].position,
                    assetType,
                  })
                }
              />
            ))}
          </div>
          <div
            style={{ minWidth: 0, position: "sticky", top: 12, overflow: "hidden" }}
          >
            <div
              style={{
                transform: selected ? "translateX(0)" : "translateX(calc(100% + 12px))",
                opacity: selected ? 1 : 0,
                transition: "transform 220ms cubic-bezier(0.16, 1, 0.3, 1), opacity 160ms ease-out",
                pointerEvents: selected ? "auto" : "none",
              }}
            >
              {selected && (
                <ShootDetail
                  shoot={selected}
                  onClose={() => setSelectedShootId(null)}
                  onRevalidate={async (position, assetType) => {
                    if (!idToken) return
                    const key = `${selected.shoot_id}|${position}|${assetType}`
                    if (inFlightRef.current.has(key)) return
                    inFlightRef.current.add(key)
                    try {
                      const newState = await client.shoots.revalidate(selected.shoot_id, position, assetType)
                      setShoots(prev => prev.map(s => {
                        if (s.shoot_id !== selected.shoot_id) return s
                        return {
                          ...s,
                          scenes: s.scenes.map(sc => sc.position !== position ? sc : {
                            ...sc,
                            assets: sc.assets.map(a => a.asset_type === assetType ? newState : a),
                          }),
                        }
                      }))
                    } catch (e) {
                      setError(formatApiError(e, "Revalidate"))
                    } finally {
                      inFlightRef.current.delete(key)
                    }
                  }}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {popoverCell && (
        <ValidityPopover
          shoot={shoots.find(s => s.shoot_id === popoverCell.shootId)!}
          position={popoverCell.position}
          assetType={popoverCell.assetType}
          onClose={() => setPopoverCell(null)}
          onRevalidate={async () => {
            if (!idToken) return
            const key = `${popoverCell.shootId}|${popoverCell.position}|${popoverCell.assetType}`
            if (inFlightRef.current.has(key)) return
            inFlightRef.current.add(key)
            try {
              const newState = await client.shoots.revalidate(popoverCell.shootId, popoverCell.position, popoverCell.assetType)
              setShoots(prev => prev.map(s => {
                if (s.shoot_id !== popoverCell.shootId) return s
                return {
                  ...s,
                  scenes: s.scenes.map(sc => sc.position !== popoverCell.position ? sc : {
                    ...sc,
                    assets: sc.assets.map(a => a.asset_type === popoverCell.assetType ? newState : a),
                  }),
                }
              }))
            } catch (e) {
              setError(formatApiError(e, "Revalidate"))
            } finally {
              inFlightRef.current.delete(key)
            }
          }}
        />
      )}
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────────────────
function EmptyState({ filter }: { filter: string }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "48px 0",
        fontSize: 13,
        color: "var(--color-text-muted)",
      }}
    >
      <Film size={24} aria-hidden="true" style={{ opacity: 0.3, marginBottom: 8 }} />
      <div>No shoots in this window{filter !== "All" ? ` for ${filter}` : ""}.</div>
    </div>
  )
}

// ── Shoot row ─────────────────────────────────────────────────────────
interface ShootRowProps {
  shoot: Shoot
  selected: boolean
  onSelect: () => void
  onCellClick: (sceneIdx: number, assetType: AssetType) => void
}

function ShootRow({ shoot, selected, onSelect, onCellClick }: ShootRowProps) {
  const primaryStudio = shoot.scenes[0]?.studio ?? "FuckPassVR"
  const accent = studioColor(primaryStudio)
  const alert = isAlert(shoot)
  const { validated, total } = shootCompleteness(shoot)

  return (
    <button
      type="button"
      onClick={onSelect}
      className="text-left rounded transition-colors w-full"
      style={{
        display: "grid",
        gridTemplateColumns: "3px 150px minmax(0, 1fr)",
        gap: 12,
        padding: "10px 12px",
        background: selected ? "var(--color-elevated)" : "var(--color-surface)",
        border: `1px solid ${selected ? accent : "var(--color-border)"}`,
        cursor: "pointer",
      }}
    >
      <span style={{ background: alert ? "var(--color-err)" : accent, borderRadius: 2 }} aria-hidden="true" />
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: alert ? "var(--color-err)" : "var(--color-text)",
            letterSpacing: "0.02em",
          }}
        >
          {formatShootDate(shoot.shoot_date)}
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
          {shoot.female_talent}{shoot.male_talent ? ` / ${shoot.male_talent}` : ""}
        </div>
        <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
          {relativeFromHours(shoot.aging_hours)} · {validated}/{total}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        {shoot.scenes.map((scene, idx) => (
          <AssetStrip
            key={scene.position}
            scene={scene}
            onCellClick={(at) => onCellClick(idx, at)}
          />
        ))}
      </div>
    </button>
  )
}

// ── Month filter (±6 months around today, plus "Default") ────────────
function MonthFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const options = useMemo(() => {
    const now = new Date()
    const items: { key: string; label: string }[] = []
    for (let offset = -6; offset <= 6; offset++) {
      const d = new Date(now.getFullYear(), now.getMonth() + offset, 1)
      const y = d.getFullYear()
      const m = d.getMonth() + 1
      const key = `${y}-${String(m).padStart(2, "0")}`
      const label = d.toLocaleDateString(undefined, { month: "short", year: "2-digit" })
      items.push({ key, label })
    }
    return items
  }, [])

  return (
    <label
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        fontSize: 11, color: "var(--color-text-muted)",
      }}
    >
      Month
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          fontSize: 11, padding: "3px 6px", borderRadius: 4,
          background: "var(--color-surface)", color: "var(--color-text)",
          border: "1px solid var(--color-border)",
          cursor: "pointer",
        }}
      >
        <option value="">Default (this + next)</option>
        {options.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
      </select>
    </label>
  )
}

// ── Asset legend (rendered once above the list) ──────────────────────
function AssetLegend() {
  return (
    <div
      aria-hidden="true"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 12px",
        color: "var(--color-text-faint)",
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
      }}
    >
      {/* spacer for the shoot-metadata column (date/name) */}
      <span style={{ width: 150 + 12, flexShrink: 0 }} />
      {/* spacer for the grail_tab / scene_type chip (64px + 8px gap) */}
      <span style={{ width: 64 + 8, flexShrink: 0 }} />
      {PHASES.map((phase, pi) => (
        <div
          key={phase.name}
          style={{
            display: "flex",
            gap: CELL_GAP,
            marginRight: pi < PHASES.length - 1 ? PHASE_GAP : 0,
            alignItems: "center",
          }}
        >
          <span
            style={{
              width: phase.assets.length * (16 + CELL_GAP) - CELL_GAP,
              color: "var(--color-text-muted)",
              textAlign: "center",
            }}
          >
            {phase.name}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Asset strip (11 cells in 3 phase clusters) ────────────────────────
interface AssetStripProps {
  scene: BoardShootScene
  onCellClick: (assetType: AssetType) => void
}

function AssetStrip({ scene, onCellClick }: AssetStripProps) {
  const assetsByType = new Map(scene.assets.map(a => [a.asset_type, a]))
  const accent = studioColor(scene.studio)

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 700,
          color: accent,
          letterSpacing: "0.05em",
          width: 64,
          flexShrink: 0,
          textTransform: "uppercase",
        }}
      >
        {scene.grail_tab || scene.studio.slice(0, 4).toUpperCase()} · {scene.scene_type}
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        {PHASES.map((phase, pi) => (
          <div
            key={phase.name}
            style={{
              display: "flex",
              gap: CELL_GAP,
              marginRight: pi < PHASES.length - 1 ? PHASE_GAP : 0,
            }}
          >
            {phase.assets.map(at => {
              const a = assetsByType.get(at)
              const status: AssetStatus = a?.status ?? "not_present"
              const hasWarn = !!a && a.validity.some(v => v.status === "warn")
              const color = statusColor(status, hasWarn)
              const applies = cellApplies(at, scene.scene_type)
              // Irrelevant cells: dashed placeholder, no click, muted — keeps
              // the 11-cell grid aligned with the legend but signals N/A.
              if (!applies) {
                return (
                  <span
                    key={at}
                    aria-label={`${SHOOT_ASSET_LABELS[at]} (not applicable for ${scene.scene_type})`}
                    title={`${SHOOT_ASSET_LABELS[at]} — N/A for ${scene.scene_type}`}
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: 3,
                      border: "1px dashed var(--color-border)",
                      background: "transparent",
                      opacity: 0.3,
                      flexShrink: 0,
                    }}
                  />
                )
              }
              return (
                <span
                  key={at}
                  role="button"
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); onCellClick(at) }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.stopPropagation()
                      onCellClick(at)
                    }
                  }}
                  title={`${phase.name} — ${SHOOT_ASSET_LABELS[at]}: ${STATUS_LABEL[status]}${hasWarn ? " (warnings)" : ""}`}
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: 3,
                    border: `1px solid ${color}`,
                    background: status === "not_present" ? "transparent" : `color-mix(in srgb, ${color} 24%, transparent)`,
                    color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  {statusIcon(status, hasWarn)}
                </span>
              )
            })}
          </div>
        ))}
      </div>
      {scene.scene_id ? (
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>
          {scene.scene_id}
        </span>
      ) : (
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontStyle: "italic", marginLeft: "auto" }}>
          pending Grail
        </span>
      )}
    </div>
  )
}

// ── Validity popover (click a strip cell) ─────────────────────────────
interface ValidityPopoverProps {
  shoot: Shoot
  position: number
  assetType: AssetType
  onClose: () => void
  onRevalidate: () => Promise<void>
}

function ValidityPopover({ shoot, position, assetType, onClose, onRevalidate }: ValidityPopoverProps) {
  const scene = shoot.scenes.find(s => s.position === position)
  const state = scene?.assets.find(a => a.asset_type === assetType)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  if (!scene || !state) return null

  return (
    <div
      className="fixed inset-0 flex items-center justify-center"
      style={{ background: "oklch(0% 0 0 / 55%)", zIndex: 60 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        ref={ref}
        className="rounded-lg"
        style={{
          background: "var(--color-base)",
          border: "1px solid var(--color-border)",
          width: 420,
          maxWidth: "calc(100vw - 32px)",
          padding: "18px 22px",
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <div>
            <div style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.05em", textTransform: "uppercase" }}>
              {scene.studio} · {scene.scene_type} · {scene.scene_id || "pending Grail"}
            </div>
            <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--color-text)", margin: "2px 0 0" }}>
              {SHOOT_ASSET_LABELS[assetType]}
            </h2>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ color: "var(--color-text-muted)" }}>
            <X size={14} />
          </button>
        </div>

        <div
          className="rounded"
          style={{
            padding: "6px 10px",
            fontSize: 11,
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-muted)",
            marginBottom: 12,
          }}
        >
          <div>Status: <strong style={{ color: statusColor(state.status, state.validity.some(v => v.status === "warn")) }}>{STATUS_LABEL[state.status]}</strong></div>
          {state.first_seen_at && <div>First seen: <span style={{ fontFamily: "var(--font-mono)" }}>{state.first_seen_at.slice(0, 19)}</span></div>}
          {state.validated_at && <div>Validated: <span style={{ fontFamily: "var(--font-mono)" }}>{state.validated_at.slice(0, 19)}</span></div>}
        </div>

        {state.validity.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", padding: "8px 0" }}>
            {state.status === "validated"
              ? "All checks passed."
              : state.status === "not_present"
                ? "Not yet uploaded to MEGA."
                : "No validity issues to report."}
          </div>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
            {state.validity.map((v, i) => {
              const color = v.status === "fail" ? "var(--color-err)" : v.status === "warn" ? "var(--color-warn)" : "var(--color-ok)"
              return (
                <li
                  key={i}
                  className="rounded"
                  style={{
                    padding: "7px 10px",
                    fontSize: 11,
                    color,
                    background: `color-mix(in srgb, ${color} 8%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
                  }}
                >
                  <strong style={{ fontWeight: 600 }}>{v.check}</strong>: {v.message}
                </li>
              )
            })}
          </ul>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={async () => { setBusy(true); try { await onRevalidate() } finally { setBusy(false) } }}
            disabled={busy}
            className="px-3 py-1.5 rounded text-xs font-semibold"
            style={{
              background: "var(--color-lime)",
              color: "var(--color-base)",
              opacity: busy ? 0.5 : 1,
              cursor: busy ? "not-allowed" : "pointer",
              border: "none",
            }}
          >
            {busy ? "Checking…" : "Retry check"}
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs"
            style={{
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Shoot detail panel ────────────────────────────────────────────────
interface ShootDetailProps {
  shoot: Shoot
  onClose: () => void
  onRevalidate: (position: number, assetType: AssetType) => Promise<void>
}

function ShootDetail({ shoot, onClose, onRevalidate }: ShootDetailProps) {
  const color = studioColor(shoot.scenes[0]?.studio ?? "FuckPassVR")
  return (
    <div
      role="complementary"
      aria-label={`Shoot ${shoot.shoot_id} details`}
      style={{
        display: "flex",
        flexDirection: "column",
        maxHeight: "calc(100vh - var(--spacing-topbar) - 24px)",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "14px",
          borderBottom: "1px solid var(--color-border)",
          background: `color-mix(in srgb, ${color} 6%, var(--color-surface))`,
          flexShrink: 0,
        }}
      >
        <div className="flex items-center justify-between mb-1">
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            {formatShootDate(shoot.shoot_date)} · {shoot.source_tab}
          </div>
          <button onClick={onClose} aria-label="Close" style={{ color: "var(--color-text-muted)" }}>
            <X size={14} />
          </button>
        </div>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "var(--color-text)" }}>
          {shoot.female_talent}
          {shoot.male_talent && (
            <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}> / {shoot.male_talent}</span>
          )}
        </h2>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
          {shoot.female_agency || "—"}
          {shoot.male_agency && <> · {shoot.male_agency}</>}
        </div>
        {shoot.location && (
          <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 2 }}>
            {shoot.location}{shoot.home_owner ? ` · host: ${shoot.home_owner}` : ""}
          </div>
        )}
      </div>

      <div style={{ padding: "10px 14px", overflowY: "auto" }}>
        {shoot.scenes.map(scene => (
          <SceneAssetTable
            key={scene.position}
            scene={scene}
            onRevalidate={(at) => onRevalidate(scene.position, at)}
          />
        ))}
      </div>
    </div>
  )
}

function SceneAssetTable({
  scene,
  onRevalidate,
}: {
  scene: BoardShootScene
  onRevalidate: (assetType: AssetType) => Promise<void>
}) {
  const color = studioColor(scene.studio)
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="flex items-center gap-2 mb-2">
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.05em",
            color,
            textTransform: "uppercase",
          }}
        >
          {scene.studio} · {scene.scene_type}
        </span>
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
          {scene.scene_id || "(pending Grail row)"}
        </span>
      </div>
      <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <tbody>
          {scene.assets.filter(a => cellApplies(a.asset_type, scene.scene_type)).map(a => {
            const hasWarn = a.validity.some(v => v.status === "warn")
            const color = statusColor(a.status, hasWarn)
            return (
              <tr
                key={a.asset_type}
                style={{ borderBottom: "1px solid var(--color-border)" }}
              >
                <td style={{ padding: "6px 4px", fontSize: 11, color: "var(--color-text)" }}>
                  {SHOOT_ASSET_LABELS[a.asset_type]}
                </td>
                <td style={{ padding: "6px 4px", fontSize: 11, color, fontWeight: 500 }}>
                  {STATUS_LABEL[a.status]}{hasWarn ? ` · ${a.validity.length} note${a.validity.length === 1 ? "" : "s"}` : ""}
                </td>
                <td style={{ padding: "6px 4px", fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)", textAlign: "right" }}>
                  {a.validated_at ? a.validated_at.slice(5, 16).replace("T", " ") : ""}
                </td>
                <td style={{ padding: "6px 0 6px 6px", textAlign: "right" }}>
                  <button
                    onClick={() => { void onRevalidate(a.asset_type) }}
                    aria-label={`Recheck ${a.asset_type}`}
                    style={{
                      fontSize: 10,
                      color: "var(--color-text-muted)",
                      background: "transparent",
                      border: "1px solid var(--color-border)",
                      borderRadius: 3,
                      padding: "2px 6px",
                      cursor: "pointer",
                    }}
                  >
                    <RefreshCcw size={9} className="inline" aria-hidden="true" />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
