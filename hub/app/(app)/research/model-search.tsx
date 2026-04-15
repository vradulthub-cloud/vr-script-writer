"use client"

import { useState, useMemo, useDeferredValue } from "react"
import { ErrorAlert } from "@/components/ui/error-alert"
import type { Model } from "@/lib/api"

// ─── Rank config ─────────────────────────────────────────────────────────────

const RANK_CONFIG: Record<string, { label: string; color: string }> = {
  great:    { label: "Great",    color: "#22c55e" },
  good:     { label: "Good",     color: "#bed62f" },
  moderate: { label: "Mod",      color: "#eab308" },
  poor:     { label: "Poor",     color: "#ef4444" },
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 75) return "#22c55e"
  if (score >= 50) return "#bed62f"
  if (score >= 30) return "#eab308"
  return "#6b7280"
}

function parseActs(notes: string): string[] {
  if (!notes) return []
  if (notes.includes(",")) return notes.split(",").map(a => a.trim()).filter(Boolean)
  return [notes.trim()]
}

function urgencyLabel(lastBooked: string): { text: string; color: string } {
  if (!lastBooked) return { text: "Never booked", color: "#22c55e" }
  const match = lastBooked.match(/(\w+)\s+(\d{4})/)
  if (!match) return { text: lastBooked, color: "var(--color-text-muted)" }
  const months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
  const mIdx = months.indexOf(match[1].toLowerCase().slice(0, 3))
  const yr = parseInt(match[2])
  if (mIdx === -1 || isNaN(yr)) return { text: lastBooked, color: "var(--color-text-muted)" }
  const now = new Date()
  const ago = (now.getFullYear() - yr) * 12 + (now.getMonth() - mIdx)
  if (ago > 36) return { text: lastBooked, color: "#22c55e" }
  if (ago > 24) return { text: lastBooked, color: "#bed62f" }
  if (ago > 12) return { text: lastBooked, color: "#eab308" }
  if (ago > 6)  return { text: lastBooked, color: "#f97316" }
  return { text: lastBooked, color: "#ef4444" }
}

// ─── Babepedia portrait URL (Title_Case_Underscores.jpg) ─────────────────────

function buildPhotoUrl(name: string): string {
  const slug = name.trim().split(/\s+/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join("_")
  return `https://www.babepedia.com/pics/${slug}.jpg`
}

// ─── Circular photo with initials fallback ────────────────────────────────────

function ModelPhoto({ name, size = 28 }: { name: string; size?: number }) {
  const [failed, setFailed] = useState(false)
  const initials = name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase()).join("")

  if (failed) {
    return (
      <div
        aria-hidden="true"
        style={{
          width: size, height: size, borderRadius: "50%",
          background: "var(--color-elevated)",
          border: "1px solid var(--color-border)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: Math.round(size * 0.38), fontWeight: 600,
          color: "var(--color-text-faint)",
          flexShrink: 0, userSelect: "none",
        }}
      >
        {initials}
      </div>
    )
  }

  return (
    <img
      src={buildPhotoUrl(name)}
      alt=""
      aria-hidden="true"
      onError={() => setFailed(true)}
      style={{
        width: size, height: size, borderRadius: "50%",
        objectFit: "cover", objectPosition: "50% 10%",
        flexShrink: 0,
        border: "1px solid var(--color-border)",
      }}
    />
  )
}

// ─── Top Outreach card ─────────────────────────────────────────────────────────

function OutreachCard({
  model, isActive, onClick,
}: {
  model: Model
  isActive: boolean
  onClick: () => void
}) {
  const [imgFailed, setImgFailed] = useState(false)
  const initials = model.name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase()).join("")
  const urgency = urgencyLabel(model.last_booked)
  const rankCfg = RANK_CONFIG[model.rank.toLowerCase()]

  return (
    <button
      onClick={onClick}
      aria-pressed={isActive}
      className="text-left w-full"
      style={{
        position: "relative",
        borderRadius: 8,
        overflow: "hidden",
        background: "var(--color-surface)",
        border: `1px solid ${isActive ? "var(--color-lime)" : "var(--color-border)"}`,
        cursor: "pointer",
        padding: 0,
        transition: "border-color 0.15s",
        display: "block",
      }}
      onMouseEnter={e => {
        if (!isActive) (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.18)"
      }}
      onMouseLeave={e => {
        if (!isActive) (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)"
      }}
    >
      {/* Photo / initials */}
      {imgFailed ? (
        <div style={{
          height: 150,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "var(--color-elevated)",
          fontSize: 30, fontWeight: 700, color: "var(--color-text-faint)",
        }}>
          {initials}
        </div>
      ) : (
        <img
          src={buildPhotoUrl(model.name)}
          alt=""
          aria-hidden="true"
          onError={() => setImgFailed(true)}
          style={{
            width: "100%", height: 150,
            objectFit: "cover", objectPosition: "50% 10%",
            display: "block",
          }}
        />
      )}

      {/* Opportunity score badge */}
      <div style={{
        position: "absolute", top: 6, right: 6,
        background: scoreColor(model.opportunity_score),
        color: "#000",
        borderRadius: 10, padding: "1px 6px",
        fontSize: 10, fontWeight: 700, lineHeight: "16px",
      }}>
        {model.opportunity_score}
      </div>

      {/* Rank badge (top-left, shown for Great/Good only) */}
      {rankCfg && model.rank.toLowerCase() !== "moderate" && model.rank.toLowerCase() !== "poor" && (
        <div style={{
          position: "absolute", top: 6, left: 6,
          background: `color-mix(in srgb, ${rankCfg.color} 18%, rgba(0,0,0,0.7))`,
          color: rankCfg.color,
          border: `1px solid color-mix(in srgb, ${rankCfg.color} 35%, transparent)`,
          borderRadius: 4, padding: "1px 5px",
          fontSize: 9, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase",
        }}>
          {rankCfg.label}
        </div>
      )}

      {/* Gradient overlay — name + urgency */}
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0,
        background: "linear-gradient(transparent, rgba(0,0,0,0.88))",
        padding: "24px 8px 8px",
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700, color: "#f0ede8",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {model.name}
        </div>
        <div style={{
          fontSize: 10, marginTop: 1,
          color: urgency.color,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {urgency.text === "Never booked" ? "Never booked" : model.agency || urgency.text}
        </div>
      </div>
    </button>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

type SortKey = "score" | "name" | "last_booked" | "rank"

interface Props {
  models: Model[]
  error: string | null
}

export function ModelSearch({ models, error }: Props) {
  const [search, setSearch]             = useState("")
  const [rankFilter, setRankFilter]     = useState("All")
  const [locationFilter, setLocationFilter] = useState("All")
  const [sortKey, setSortKey]           = useState<SortKey>("score")
  const [expanded, setExpanded]         = useState<string | null>(null)
  const deferredSearch                  = useDeferredValue(search)

  const isFiltered = search !== "" || rankFilter !== "All" || locationFilter !== "All"

  // Top 8 by opportunity score — shown above the list when no filters are active
  const topOutreach = useMemo(
    () => [...models].sort((a, b) => b.opportunity_score - a.opportunity_score).slice(0, 8),
    [models]
  )

  const locations = useMemo(() => {
    const locs = new Set<string>()
    models.forEach(m => { if (m.location) locs.add(m.location) })
    return ["All", ...Array.from(locs).sort()]
  }, [models])

  const filtered = useMemo(() => {
    let list = models
    const q = deferredSearch.toLowerCase()
    if (q) {
      list = list.filter(m =>
        m.name.toLowerCase().includes(q) ||
        m.agency.toLowerCase().includes(q) ||
        m.notes.toLowerCase().includes(q)
      )
    }
    if (rankFilter !== "All") list = list.filter(m => m.rank.toLowerCase() === rankFilter.toLowerCase())
    if (locationFilter !== "All") list = list.filter(m => m.location === locationFilter)
    return list
  }, [models, deferredSearch, rankFilter, locationFilter])

  const sorted = useMemo(() => {
    const list = [...filtered]
    if (sortKey === "score")      return list.sort((a, b) => b.opportunity_score - a.opportunity_score)
    if (sortKey === "name")       return list.sort((a, b) => a.name.localeCompare(b.name))
    if (sortKey === "last_booked") {
      return list.sort((a, b) => {
        if (!a.last_booked && !b.last_booked) return 0
        if (!a.last_booked) return -1
        if (!b.last_booked) return 1
        return a.last_booked.localeCompare(b.last_booked)
      })
    }
    if (sortKey === "rank") {
      const order: Record<string, number> = { great: 0, good: 1, moderate: 2, poor: 3 }
      return list.sort((a, b) => (order[a.rank.toLowerCase()] ?? 9) - (order[b.rank.toLowerCase()] ?? 9))
    }
    return list
  }, [filtered, sortKey])

  const isActList = (notes: string) => notes.includes(",")

  return (
    <div>

      {/* ── Top Outreach grid (hidden when filters active) ───────────────────── */}
      {!isFiltered && topOutreach.length > 0 && (
        <div className="mb-7">
          <div className="flex items-center gap-2 mb-3">
            <span style={{
              fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
              textTransform: "uppercase", color: "#22c55e",
            }}>
              Top Outreach
            </span>
            <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
              Highest opportunity scores — click to expand
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            {topOutreach.map(model => (
              <OutreachCard
                key={model.name}
                model={model}
                isActive={expanded === model.name}
                onClick={() => setExpanded(expanded === model.name ? null : model.name)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Controls bar ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 mb-5" style={{ alignItems: "center" }}>
        <input
          type="text"
          placeholder="Search name, agency, acts…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-2.5 py-1.5 rounded text-xs outline-none"
          style={{
            width: 240,
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text)",
          }}
        />

        <div className="flex gap-1">
          {["All", "Great", "Good", "Moderate", "Poor"].map(r => {
            const cfg = RANK_CONFIG[r.toLowerCase()]
            const active = rankFilter === r
            return (
              <button
                key={r}
                onClick={() => setRankFilter(r)}
                className="px-2 py-1 rounded text-xs transition-colors"
                style={{
                  background: active ? (cfg ? `color-mix(in srgb, ${cfg.color} 15%, transparent)` : "var(--color-elevated)") : "transparent",
                  color: active ? (cfg?.color ?? "var(--color-text)") : "var(--color-text-faint)",
                  border: `1px solid ${active ? (cfg ? `color-mix(in srgb, ${cfg.color} 30%, transparent)` : "var(--color-border)") : "transparent"}`,
                  fontWeight: active ? 600 : 400,
                }}
              >
                {r}
              </button>
            )
          })}
        </div>

        {locations.length > 2 && (
          <select
            value={locationFilter}
            onChange={e => setLocationFilter(e.target.value)}
            className="px-2 py-1.5 rounded text-xs outline-none"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              color: locationFilter !== "All" ? "var(--color-text)" : "var(--color-text-faint)",
            }}
          >
            {locations.map(l => <option key={l} value={l}>{l === "All" ? "All locations" : l}</option>)}
          </select>
        )}

        <select
          value={sortKey}
          onChange={e => setSortKey(e.target.value as SortKey)}
          className="px-2.5 py-1.5 rounded text-xs outline-none ml-auto"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-muted)",
          }}
        >
          <option value="score">Sort: Opportunity</option>
          <option value="rank">Sort: Rank</option>
          <option value="last_booked">Sort: Last Booked</option>
          <option value="name">Sort: Name</option>
        </select>

        <span style={{ fontSize: 11, color: "var(--color-text-faint)", whiteSpace: "nowrap" }}>
          {isFiltered ? `${sorted.length} of ${models.length}` : `${models.length} models`}
        </span>
      </div>

      {/* ── Error ────────────────────────────────────────────────────────────── */}
      {error && <ErrorAlert className="mb-4">{error}</ErrorAlert>}

      {/* ── Empty ────────────────────────────────────────────────────────────── */}
      {!error && sorted.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
          No models match the current filters.
        </p>
      )}

      {/* ── Table ────────────────────────────────────────────────────────────── */}
      {!error && sorted.length > 0 && (
        <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
          {/* Header */}
          <div
            className="grid"
            style={{
              gridTemplateColumns: "52px 1fr 140px 72px 80px 80px",
              background: "var(--color-surface)",
              borderBottom: "1px solid var(--color-border)",
              padding: "6px 12px",
            }}
          >
            {["Score", "Name", "Agency", "Rate", "Location", "Last Booked"].map(h => (
              <span key={h} style={{
                fontSize: 10, fontWeight: 600, letterSpacing: "0.06em",
                textTransform: "uppercase", color: "var(--color-text-faint)",
              }}>
                {h}
              </span>
            ))}
          </div>

          {sorted.map((model, i) => {
            const isExpanded = expanded === model.name
            const isLast = i === sorted.length - 1
            const rankCfg = RANK_CONFIG[model.rank.toLowerCase()]
            const urgency = urgencyLabel(model.last_booked)
            const acts = parseActs(model.notes)
            const isActualActList = isActList(model.notes)

            return (
              <div key={model.name}>
                {/* Row */}
                <div
                  className="grid cursor-pointer transition-colors"
                  style={{
                    gridTemplateColumns: "52px 1fr 140px 72px 80px 80px",
                    padding: "8px 12px",
                    borderBottom: (!isExpanded && !isLast) ? "1px solid var(--color-border-subtle)" : undefined,
                    background: isExpanded ? "var(--color-surface)" : undefined,
                    alignItems: "center",
                  }}
                  onClick={() => setExpanded(isExpanded ? null : model.name)}
                  onMouseEnter={e => { if (!isExpanded) (e.currentTarget as HTMLElement).style.background = "var(--color-elevated)" }}
                  onMouseLeave={e => { if (!isExpanded) (e.currentTarget as HTMLElement).style.background = "" }}
                >
                  {/* Score */}
                  <span style={{
                    fontSize: 18, fontWeight: 700, lineHeight: 1,
                    fontVariantNumeric: "tabular-nums",
                    color: scoreColor(model.opportunity_score),
                  }}>
                    {model.opportunity_score}
                  </span>

                  {/* Photo + Name + rank */}
                  <div style={{ minWidth: 0, display: "flex", alignItems: "center", gap: 8 }}>
                    <ModelPhoto name={model.name} size={26} />
                    <div style={{ minWidth: 0 }}>
                      <div className="flex items-center gap-2">
                        <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text)" }}>
                          {model.name}
                        </span>
                        {rankCfg && (
                          <span style={{
                            fontSize: 9, fontWeight: 700, letterSpacing: "0.06em",
                            textTransform: "uppercase", color: rankCfg.color,
                            background: `color-mix(in srgb, ${rankCfg.color} 12%, transparent)`,
                            border: `1px solid color-mix(in srgb, ${rankCfg.color} 25%, transparent)`,
                            borderRadius: 2, padding: "1px 4px",
                          }}>
                            {rankCfg.label}
                          </span>
                        )}
                        {model.age && (
                          <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                            {model.age}
                          </span>
                        )}
                      </div>
                      {!isActualActList && model.notes && (
                        <p className="line-clamp-1" style={{
                          fontSize: 10, color: "var(--color-text-faint)", marginTop: 1,
                        }}>
                          {model.notes}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Agency */}
                  <div style={{ minWidth: 0 }}>
                    {model.agency_link ? (
                      <a
                        href={model.agency_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="line-clamp-1 block"
                        style={{ fontSize: 11, color: "var(--color-lime)", textDecoration: "none" }}
                      >
                        {model.agency || "—"}
                      </a>
                    ) : (
                      <span className="line-clamp-1 block" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                        {model.agency || "—"}
                      </span>
                    )}
                  </div>

                  {/* Rate */}
                  <span className="font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {model.rate || "—"}
                  </span>

                  {/* Location */}
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {model.location || "—"}
                  </span>

                  {/* Last booked */}
                  <span style={{
                    fontSize: 11,
                    color: urgency.color,
                    fontWeight: urgency.color === "#22c55e" ? 500 : 400,
                  }}>
                    {urgency.text}
                  </span>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div
                    style={{
                      padding: "12px 12px 14px 12px",
                      background: "var(--color-surface)",
                      borderBottom: !isLast ? "1px solid var(--color-border-subtle)" : undefined,
                      display: "flex", gap: 16, alignItems: "flex-start",
                    }}
                  >
                    {/* Larger photo */}
                    <ModelPhoto name={model.name} size={72} />

                    <div style={{ flex: 1, minWidth: 0 }}>
                      {model.bookings_count && (
                        <p style={{ fontSize: 11, color: "var(--color-text-faint)", marginBottom: 8 }}>
                          <span style={{ color: "var(--color-text-muted)" }}>{model.bookings_count}</span>
                          {" "}booking{model.bookings_count !== "1" ? "s" : ""} with us
                          {" · "}
                          <span style={{ color: urgency.color }}>
                            Last: {model.last_booked || "never"}
                          </span>
                        </p>
                      )}

                      {isActualActList && acts.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {acts.map(act => (
                            <span
                              key={act}
                              style={{
                                fontSize: 10, color: "var(--color-text-muted)",
                                background: "var(--color-elevated)",
                                border: "1px solid var(--color-border-subtle)",
                                borderRadius: 3, padding: "2px 6px", whiteSpace: "nowrap",
                              }}
                            >
                              {act}
                            </span>
                          ))}
                        </div>
                      )}

                      {!isActualActList && model.notes && (
                        <p style={{
                          fontSize: 12, color: "var(--color-text-muted)",
                          lineHeight: 1.5, fontStyle: "italic",
                        }}>
                          "{model.notes}"
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
