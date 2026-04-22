"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { CheckCircle2, AlertTriangle, Circle, Clock, X, RefreshCcw, Film, Wand2, Check } from "lucide-react"
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
import { PageHeader } from "@/components/ui/page-header"
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
  /** Eclatech v2 layout: clean roster rows (talent / progress / status),
   *  per-asset cell matrix hidden behind a click-to-expand. Default "v1"
   *  renders the legacy always-visible-cells layout. */
  variant?: "v1" | "v2"
  /** When the board is embedded under ShootsV2View, the page owns the
   *  studio filter so one pick drives both the calendar and the roster.
   *  When this prop is set the local filter state is ignored. */
  studioFilter?: string
  /** Hide the PageHeader when the parent already renders one. */
  hideHeader?: boolean
}

export function ShootBoard({
  initialShoots,
  error: initialError,
  idToken: serverToken,
  variant = "v1",
  studioFilter: externalStudioFilter,
  hideHeader,
}: Props) {
  const idToken = useIdToken(serverToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [shoots, setShoots] = useState<Shoot[]>(initialShoots)
  const [error, setError] = useState<string | null>(initialError)
  const [internalStudioFilter, setInternalStudioFilter] = useState<string>("All")
  const studioFilter = externalStudioFilter ?? internalStudioFilter
  const setStudioFilter = externalStudioFilter !== undefined ? () => {} : setInternalStudioFilter
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const toggleExpanded = useCallback((shootId: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(shootId)) next.delete(shootId); else next.add(shootId)
      return next
    })
  }, [])
  // Month filter key: "" = default window (current + next month), or a
  // specific month in YYYY-MM form for a custom 1-month view.
  const [monthFilter, setMonthFilter] = useState<string>("")
  const [selectedShootId, setSelectedShootId] = useState<string | null>(null)
  // Separate state for the modal-based details view so it doesn't fight with
  // the slide-in panel (used by v1 row-click). "Open details" on v2 rows
  // opens the modal; v1's row click still opens the slide-in.
  const [modalShootId, setModalShootId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshFailures, setRefreshFailures] = useState(0)
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null)
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

  const modalShoot = useMemo(
    () => shoots.find(s => s.shoot_id === modalShootId) ?? null,
    [shoots, modalShootId],
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
      setLastRefreshed(new Date())
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
      {!hideHeader && (
        <PageHeader
          title="Shoot Tracker"
          eyebrow={`${filtered.length} in window · ${refreshing ? "refreshing" : "auto-refresh 30s"}`}
          studioAccent={studioFilter !== "All" ? studioFilter : undefined}
          actions={
            <>
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
              <MonthFilter value={monthFilter} onChange={setMonthFilter} />
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                <button
                  onClick={() => { void refresh() }}
                  disabled={refreshing}
                  className="px-2.5 py-1 rounded text-xs transition-colors"
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    background: "transparent",
                    color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                    cursor: refreshing ? "not-allowed" : "pointer",
                  }}
                >
                  <RefreshCcw
                    size={11}
                    aria-hidden="true"
                    style={{ animation: refreshing ? "spin 0.8s linear infinite" : undefined }}
                  />
                  {refreshing ? "Refreshing…" : "Refresh"}
                </button>
                {lastRefreshed && !refreshing && (
                  <span style={{ fontSize: 9, color: "var(--color-text-faint)", letterSpacing: "0.02em" }}>
                    updated {lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
            </>
          }
        />
      )}

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
          {/* TKT-0104: horizontal scroll wrapper with right-fade affordance */}
          <div style={{ minWidth: 0, position: "relative" }}>
            <div style={{
              overflowX: "auto",
              display: "flex", flexDirection: "column", gap: 8,
              paddingBottom: 4,
            }}>
            {variant === "v1" && <AssetLegend />}
            {filtered.map(shoot => (
              variant === "v2" ? (
                <ShootRowV2
                  key={shoot.shoot_id}
                  shoot={shoot}
                  expanded={expanded.has(shoot.shoot_id)}
                  onToggle={() => toggleExpanded(shoot.shoot_id)}
                  onOpenDetails={() => setModalShootId(shoot.shoot_id)}
                  onCellClick={(sceneIdx, assetType) =>
                    setPopoverCell({
                      shootId: shoot.shoot_id,
                      position: shoot.scenes[sceneIdx].position,
                      assetType,
                    })
                  }
                />
              ) : (
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
              )
            ))}
            </div>
            {/* Right-fade scroll affordance */}
            <div aria-hidden="true" style={{
              position: "absolute", top: 0, right: 0, bottom: 0, width: 32,
              background: "linear-gradient(to right, transparent, var(--color-bg))",
              pointerEvents: "none",
            }} />
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
                  idToken={idToken}
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

      {modalShoot && (
        <ShootDetailsModal
          shoot={modalShoot}
          idToken={idToken}
          onClose={() => setModalShootId(null)}
          onRevalidate={async (position, assetType) => {
            if (!idToken) return
            const key = `${modalShoot.shoot_id}|${position}|${assetType}`
            if (inFlightRef.current.has(key)) return
            inFlightRef.current.add(key)
            try {
              const newState = await client.shoots.revalidate(modalShoot.shoot_id, position, assetType)
              setShoots(prev => prev.map(s => {
                if (s.shoot_id !== modalShoot.shoot_id) return s
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

// ── Shoot row (v2 — clean roster, cells behind click-to-expand) ──────
interface ShootRowV2Props {
  shoot: Shoot
  expanded: boolean
  onToggle: () => void
  onOpenDetails: () => void
  onCellClick: (sceneIdx: number, assetType: AssetType) => void
}

function ShootRowV2({ shoot, expanded, onToggle, onOpenDetails, onCellClick }: ShootRowV2Props) {
  const primaryStudio = shoot.scenes[0]?.studio ?? "FuckPassVR"
  const accent = studioColor(primaryStudio)
  const alert = isAlert(shoot)
  const { validated, total } = shootCompleteness(shoot)
  const progress = total > 0 ? Math.round((validated / total) * 100) : 0
  const abbr = (shoot.scenes[0]?.grail_tab || primaryStudio.slice(0, 4)).toUpperCase()
  const statusKey = progress === 100 ? "ok" : alert ? "err" : progress > 0 ? "progress" : "warn"
  const statusLabel = progress === 100 ? "WRAPPED" : alert ? "OVERDUE" : progress > 0 ? "ACTIVE" : "PREP"

  return (
    <div
      style={{
        border: `1px solid ${expanded ? "var(--color-border)" : alert ? "var(--color-err)" : "var(--color-border-subtle)"}`,
        background: expanded
          ? "var(--color-elevated)"
          : alert
            ? "color-mix(in srgb, var(--color-err) 6%, var(--color-surface))"
            : "var(--color-surface)",
        transition: "background 120ms ease",
      }}
    >
      {/* Clickable summary row */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        style={{
          width: "100%",
          display: "grid",
          gridTemplateColumns: "72px 140px minmax(0, 1fr) 160px 110px 80px 20px",
          columnGap: 14,
          alignItems: "center",
          padding: "12px 14px",
          background: "transparent",
          border: "none",
          textAlign: "left",
          cursor: "pointer",
          color: "inherit",
        }}
      >
        {/* Studio chip */}
        <span className={`ec-studio-chip ${abbr.toLowerCase()}`} style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", color: accent,
        }}>
          {abbr}
        </span>

        {/* Date */}
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", fontVariantNumeric: "tabular-nums" }}>
          {formatShootDate(shoot.shoot_date)}
        </div>

        {/* Talent (flex column) */}
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 13, color: "var(--color-text)", overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {shoot.female_talent || "—"}
            {shoot.male_talent && <span style={{ color: "var(--color-text-muted)" }}> / {shoot.male_talent}</span>}
          </div>
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
            {shoot.scenes.length} scene{shoot.scenes.length === 1 ? "" : "s"} · {relativeFromHours(shoot.aging_hours)}
          </div>
        </div>

        {/* Progress bar + count */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 12, fontVariantNumeric: "tabular-nums",
            color: "var(--color-text)", minWidth: 48, textAlign: "right",
          }}>
            {validated}/{total}
          </span>
          <div style={{
            flex: 1, height: 4, borderRadius: 2,
            background: "var(--color-border-subtle)", overflow: "hidden",
          }}>
            <div style={{
              width: "100%",
              height: "100%",
              background: alert ? "var(--color-err)" : accent,
              transform: `scaleX(${progress / 100})`,
              transformOrigin: "left center",
              transition: "transform 180ms var(--ease-out-quart)",
            }} />
          </div>
          <span style={{
            fontSize: 11, fontVariantNumeric: "tabular-nums",
            color: "var(--color-text-muted)", minWidth: 34, textAlign: "right",
          }}>
            {progress}%
          </span>
        </div>

        {/* Status pill */}
        <span className="ec-pill" data-s={statusKey} style={{ justifySelf: "start" }}>
          <span className="d" />
          {statusLabel}
        </span>

        {/* Aging */}
        {alert ? (
          <span className="ec-age" data-hot style={{ justifySelf: "start" }}>
            {Math.floor(shoot.aging_hours / 24)}d
          </span>
        ) : (
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
            {shoot.aging_hours > 0 ? `${Math.floor(shoot.aging_hours / 24)}d` : "fresh"}
          </span>
        )}

        {/* Expand chevron */}
        <span aria-hidden="true" style={{
          fontSize: 10, color: "var(--color-text-muted)",
          transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform 120ms ease",
          justifySelf: "center",
        }}>
          ▶
        </span>
      </button>

      {/* Expanded: per-asset cells (one strip per scene) + details link */}
      {expanded && (
        <div style={{
          padding: "10px 14px 14px 14px",
          borderTop: "1px solid var(--color-border-subtle)",
          display: "flex", flexDirection: "column", gap: 8,
        }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            fontSize: 9, letterSpacing: "0.14em", color: "var(--color-text-faint)",
            textTransform: "uppercase",
          }}>
            <span>Asset phases · click a cell to revalidate</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onOpenDetails() }}
              style={{
                background: "transparent", border: "none", cursor: "pointer",
                fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase",
                color: "var(--color-lime)", padding: 0,
              }}
            >
              Open details →
            </button>
          </div>
          {shoot.scenes.map((scene, idx) => (
            <AssetStrip
              key={scene.position}
              scene={scene}
              onCellClick={(at) => onCellClick(idx, at)}
              showLabels
            />
          ))}
        </div>
      )}
    </div>
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

// ── Asset legend (rendered once above the list, sticky) ─────────────
function AssetLegend() {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "var(--color-bg)",
        borderBottom: "1px solid var(--color-border-subtle)",
        paddingBottom: 6,
        marginBottom: -2,
      }}
    >
      {/* Phase column headers */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 12px 2px",
          color: "var(--color-text-faint)",
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        <span style={{ width: 150 + 12, flexShrink: 0 }} />
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
      {/* Status legend */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "0 12px", fontSize: 9, color: "var(--color-text-faint)",
      }}>
        {([
          ["var(--color-border)", "not yet"],
          ["var(--color-warn)",   "in flight"],
          ["var(--color-ok)",     "validated"],
          ["var(--color-err)",    "blocked"],
        ] as [string, string][]).map(([color, label]) => (
          <span key={label} style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{
              display: "inline-block", width: 8, height: 8, borderRadius: 2,
              background: color, flexShrink: 0,
            }} />
            {label}
          </span>
        ))}
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{
            display: "inline-block", width: 8, height: 8, borderRadius: 2,
            border: "1px dashed var(--color-border)", opacity: 0.4, flexShrink: 0,
          }} />
          n/a
        </span>
      </div>
    </div>
  )
}

// ── Asset strip (11 cells in 3 phase clusters) ────────────────────────
interface AssetStripProps {
  scene: BoardShootScene
  onCellClick: (assetType: AssetType) => void
  /** V2 mode: render a short 2–3 char asset code below each cell so users
   *  don't have to click to learn what a cell represents. */
  showLabels?: boolean
}

/** Short, reader-glanceable labels for each asset cell when rendered below
 *  the 16px square. 2–3 chars fits without truncation. */
const ASSET_SHORT: Record<AssetType, string> = {
  script_done:          "SCR",
  call_sheet_sent:      "CS",
  legal_run:            "LEG",
  grail_run:            "GR",
  bg_edit_uploaded:     "BG",
  solo_uploaded:        "SOLO",
  title_done:           "TTL",
  encoded_uploaded:     "ENC",
  photoset_uploaded:    "PHO",
  storyboard_uploaded:  "STB",
  legal_docs_uploaded:  "DOC",
}

function AssetStrip({ scene, onCellClick, showLabels = false }: AssetStripProps) {
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
              const shortLabel = ASSET_SHORT[at]
              // Wrap the cell in a vertical column when labels are shown so the
              // short code sits directly under its cell. Width grows to 28px so
              // 3–4 char codes ("SOLO") don't truncate.
              const wrapperStyle: React.CSSProperties = showLabels
                ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 3, width: 28, flexShrink: 0 }
                : { display: "contents" }
              const cellNode = !applies ? (
                <span
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
              ) : (
                <span
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
              if (!showLabels) return <span key={at} style={{ display: "contents" }}>{cellNode}</span>
              return (
                <div key={at} style={wrapperStyle}>
                  {cellNode}
                  <span
                    aria-hidden="true"
                    style={{
                      fontSize: 8,
                      lineHeight: 1,
                      letterSpacing: "0.06em",
                      fontWeight: 600,
                      color: applies ? "var(--color-text-muted)" : "var(--color-text-faint)",
                      textTransform: "uppercase",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {shortLabel}
                  </span>
                </div>
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
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  if (!scene || !state || !mounted) return null

  const accent = statusColor(state.status, state.validity.some(v => v.status === "warn"))

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="asset-modal-title"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0, 0, 0, 0.72)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fadeIn var(--duration-base) var(--ease-out-expo) both",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(480px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: accent,
                marginBottom: 6,
              }}
            >
              {scene.studio} · {scene.scene_type} · {scene.scene_id || "pending Grail"}
            </div>
            <h2
              id="asset-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 800,
                fontSize: 22,
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              {SHOOT_ASSET_LABELS[assetType]}
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 14, overflowY: "auto", flex: "1 1 auto" }}>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 12, rowGap: 4, fontSize: 11 }}>
            <MetaRow label="Status" value={STATUS_LABEL[state.status]} valueColor={accent} />
            {state.first_seen_at && <MetaRow label="First seen" value={state.first_seen_at.slice(0, 19)} mono />}
            {state.validated_at && <MetaRow label="Validated" value={state.validated_at.slice(0, 19)} mono />}
          </div>

          <div>
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--color-text-faint)",
                marginBottom: 6,
              }}
            >
              Validity checks
            </div>
            {state.validity.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: 0, lineHeight: 1.5 }}>
                {state.status === "validated"
                  ? "All checks passed."
                  : state.status === "not_present"
                    ? "Not yet uploaded to MEGA."
                    : "No validity issues to report."}
              </p>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                {state.validity.map((v, i) => {
                  const color = v.status === "fail" ? "var(--color-err)" : v.status === "warn" ? "var(--color-warn)" : "var(--color-ok)"
                  return (
                    <li
                      key={i}
                      style={{
                        padding: "8px 10px",
                        fontSize: 12,
                        color,
                        background: `color-mix(in srgb, ${color} 8%, transparent)`,
                        border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
                      }}
                    >
                      <strong style={{ fontWeight: 700 }}>{v.check}</strong>: {v.message}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            background: "var(--color-surface)",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: "pointer",
            }}
          >
            Close
          </button>
          <button
            onClick={async () => { setBusy(true); try { await onRevalidate() } finally { setBusy(false) } }}
            disabled={busy}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-lime)",
              color: "var(--color-lime-ink)",
              border: "1px solid var(--color-lime)",
              opacity: busy ? 0.6 : 1,
              cursor: busy ? "wait" : "pointer",
            }}
          >
            {busy ? "Checking…" : "Retry check"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function MetaRow({ label, value, mono, valueColor }: { label: string; value: string; mono?: boolean; valueColor?: string }) {
  return (
    <>
      <span
        style={{
          color: "var(--color-text-faint)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          fontSize: 9,
          fontWeight: 700,
          alignSelf: "center",
        }}
      >
        {label}
      </span>
      <span
        style={{
          color: valueColor ?? "var(--color-text)",
          fontFamily: mono ? "var(--font-mono)" : undefined,
          fontSize: 12,
          fontWeight: valueColor ? 700 : 500,
        }}
      >
        {value}
      </span>
    </>
  )
}

// ── Shoot details modal ───────────────────────────────────────────────
// Wraps the same ShootDetail content used by the v1 slide-in panel in a
// centered modal shell. Triggered by "Open details →" on v2 roster rows.
// Portals to <body> to escape main's transformed ancestor (page fadeIn)
// and pins the header while the body scrolls.
function ShootDetailsModal({
  shoot,
  idToken,
  onClose,
  onRevalidate,
}: {
  shoot: Shoot
  idToken?: string
  onClose: () => void
  onRevalidate: (position: number, assetType: AssetType) => Promise<void>
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  if (!mounted) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Shoot ${shoot.shoot_id} details`}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0, 0, 0, 0.72)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fadeIn var(--duration-base) var(--ease-out-expo) both",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(820px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
        }}
      >
        {/* Re-using ShootDetail — it already handles scenes, asset grid, and
            title regeneration. We swap its outer container style so it fits
            the modal rather than the slide-in panel. */}
        <ShootDetail
          shoot={shoot}
          idToken={idToken}
          onClose={onClose}
          onRevalidate={onRevalidate}
        />
      </div>
    </div>,
    document.body,
  )
}

// ── Shoot detail panel ────────────────────────────────────────────────
interface ShootDetailProps {
  shoot: Shoot
  idToken?: string
  onClose: () => void
  onRevalidate: (position: number, assetType: AssetType) => Promise<void>
}

function ShootDetail({ shoot, idToken, onClose, onRevalidate }: ShootDetailProps) {
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
            idToken={idToken}
            onRevalidate={(at) => onRevalidate(scene.position, at)}
          />
        ))}
      </div>
    </div>
  )
}

function SceneAssetTable({
  scene,
  idToken,
  onRevalidate,
}: {
  scene: BoardShootScene
  idToken?: string
  onRevalidate: (assetType: AssetType) => Promise<void>
}) {
  const color = studioColor(scene.studio)
  const [title, setTitle] = useState(scene.title)
  const [genTitle, setGenTitle] = useState("")
  const [genBusy, setGenBusy] = useState<"idle" | "loading" | "saving">("idle")
  const [genErr, setGenErr] = useState<string | null>(null)

  // Scene-level title-gen only applies once the scene has a Grail row; until
  // then there's no `id` the backend can resolve to a scene record.
  const canGenerate = !!scene.scene_id

  async function runGenerate() {
    if (!scene.scene_id) return
    setGenBusy("loading")
    setGenErr(null)
    try {
      const { title: t } = await api(idToken ?? null).scenes.generateTitle(scene.scene_id, {})
      setGenTitle(t)
    } catch (e) {
      setGenErr(formatApiError(e, "Title"))
    } finally {
      setGenBusy("idle")
    }
  }

  async function runApply() {
    if (!scene.scene_id || !genTitle) return
    setGenBusy("saving")
    try {
      await api(idToken ?? null).scenes.updateTitle(scene.scene_id, genTitle)
      setTitle(genTitle)
      setGenTitle("")
    } catch (e) {
      setGenErr(formatApiError(e, "Save"))
    } finally {
      setGenBusy("idle")
    }
  }

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

      {/* Title row with inline generator */}
      <div
        className="flex items-center gap-2 mb-2"
        style={{
          padding: "6px 8px",
          borderRadius: 4,
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
        }}
      >
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600, flexShrink: 0 }}>
          Title
        </span>
        <span style={{ flex: 1, fontSize: 12, color: title ? "var(--color-text)" : "var(--color-text-faint)", fontStyle: title ? "normal" : "italic", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {title || "—"}
        </span>
        <button
          onClick={runGenerate}
          disabled={!canGenerate || genBusy !== "idle"}
          title={canGenerate ? "Generate title from script" : "Scene needs a Grail row first"}
          aria-label="Generate title"
          style={{
            flexShrink: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            padding: "2px 7px",
            borderRadius: 3,
            background: "transparent",
            color: !canGenerate ? "var(--color-text-faint)" : genBusy === "loading" ? "var(--color-text-faint)" : color,
            border: `1px solid ${!canGenerate ? "var(--color-border)" : `color-mix(in srgb, ${color} 35%, transparent)`}`,
            cursor: !canGenerate || genBusy !== "idle" ? "not-allowed" : "pointer",
          }}
        >
          <Wand2 size={10} aria-hidden="true" />
          {genBusy === "loading" ? "…" : "Generate"}
        </button>
      </div>

      {(genTitle || genErr) && (
        <div
          className="flex items-center gap-2 mb-2"
          style={{
            padding: "6px 8px",
            borderRadius: 4,
            background: "var(--color-elevated)",
            border: `1px solid color-mix(in srgb, ${color} 30%, var(--color-border))`,
          }}
        >
          {genErr ? (
            <>
              <span style={{ flex: 1, fontSize: 11, color: "var(--color-err)" }}>{genErr}</span>
              <button onClick={() => { setGenErr(null); setGenTitle("") }} aria-label="Dismiss" style={{ color: "var(--color-text-faint)" }}>
                <X size={11} aria-hidden="true" />
              </button>
            </>
          ) : (
            <>
              <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: "var(--color-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={genTitle}>
                {genTitle}
              </span>
              <button
                onClick={runApply}
                disabled={genBusy === "saving"}
                aria-label="Apply title"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 3,
                  fontSize: 10,
                  padding: "2px 7px",
                  borderRadius: 3,
                  background: "var(--color-lime)",
                  color: "var(--color-lime-ink)",
                  fontWeight: 600,
                  border: "none",
                  cursor: genBusy === "saving" ? "wait" : "pointer",
                }}
              >
                <Check size={10} aria-hidden="true" />
                {genBusy === "saving" ? "…" : "Apply"}
              </button>
              <button
                onClick={() => setGenTitle("")}
                aria-label="Discard"
                style={{
                  fontSize: 10,
                  padding: "2px 6px",
                  borderRadius: 3,
                  background: "transparent",
                  color: "var(--color-text-faint)",
                  border: "1px solid var(--color-border)",
                  cursor: "pointer",
                }}
              >
                Discard
              </button>
            </>
          )}
        </div>
      )}
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
