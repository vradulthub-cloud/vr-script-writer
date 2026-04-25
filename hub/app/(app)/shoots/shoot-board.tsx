"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Film, RefreshCcw } from "lucide-react"
import { api, type Shoot, type AssetType } from "@/lib/api"
import { studioColor } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { PageHeader } from "@/components/ui/page-header"
import { formatApiError } from "@/lib/errors"
import { POLL_MS, STUDIOS } from "./shoot-utils"
import { MonthFilter } from "./month-filter"
import { AssetLegend } from "./asset-legend"
import { ShootRow, ShootRowV2 } from "./shoot-row"
import { ShootDetail, ShootDetailsModal } from "./shoot-detail"
import { ValidityPopover } from "./validity-popover"

interface Props {
  initialShoots: Shoot[]
  error: string | null
  idToken: string | undefined
  variant?: "v1" | "v2"
  studioFilter?: string
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
  const [monthFilter, setMonthFilter] = useState<string>("")
  const [selectedShootId, setSelectedShootId] = useState<string | null>(null)
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
        const [y, m] = monthFilter.split("-").map(Number)
        const first = new Date(y, m - 1, 1)
        const last  = new Date(y, m, 0)
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
      if (refreshFailures >= 1) {
        setError(formatApiError(e, "Refresh"))
      }
    } finally {
      setRefreshing(false)
    }
  }, [client, idToken, monthFilter, refreshFailures])

  useEffect(() => { void refresh() }, [monthFilter])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const id = setInterval(() => { void refresh() }, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === "visible") void refresh()
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
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

  async function handleRevalidate(shootId: string, position: number, assetType: AssetType) {
    if (!idToken) return
    const key = `${shootId}|${position}|${assetType}`
    if (inFlightRef.current.has(key)) return
    inFlightRef.current.add(key)
    try {
      const newState = await client.shoots.revalidate(shootId, position, assetType)
      setShoots(prev => prev.map(s => {
        if (s.shoot_id !== shootId) return s
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
  }

  return (
    <div>
      {!hideHeader && (
        <PageHeader
          title="Shoot Tracker"
          eyebrow={`${filtered.length} in window · ${refreshing ? "refreshing" : "auto-refresh 60s"}`}
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
            <div aria-hidden="true" style={{
              position: "absolute", top: 0, right: 0, bottom: 0, width: 32,
              background: "linear-gradient(to right, transparent, var(--color-bg))",
              pointerEvents: "none",
            }} />
          </div>
          <div style={{ minWidth: 0, position: "sticky", top: 12, overflow: "hidden" }}>
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
                  onRevalidate={(position, assetType) => handleRevalidate(selected.shoot_id, position, assetType)}
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
          onRevalidate={(position, assetType) => handleRevalidate(modalShoot.shoot_id, position, assetType)}
        />
      )}

      {popoverCell && (
        <ValidityPopover
          shoot={shoots.find(s => s.shoot_id === popoverCell.shootId)!}
          position={popoverCell.position}
          assetType={popoverCell.assetType}
          onClose={() => setPopoverCell(null)}
          onRevalidate={() => handleRevalidate(popoverCell.shootId, popoverCell.position, popoverCell.assetType)}
        />
      )}
    </div>
  )
}

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
