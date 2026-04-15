"use client"

import { useState, useMemo, useDeferredValue, useCallback } from "react"
import { ErrorAlert } from "@/components/ui/error-alert"
import { api, type Model, type ModelProfile } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"

// ─── Rank config ─────────────────────────────────────────────────────────────

const RANK_CONFIG: Record<string, { label: string; color: string }> = {
  great:    { label: "Great",    color: "#22c55e" },
  good:     { label: "Good",     color: "#bed62f" },
  moderate: { label: "Mod",      color: "#eab308" },
  poor:     { label: "Poor",     color: "#ef4444" },
}

// ─── Bio fields to display (in order) ────────────────────────────────────────

const BIO_FIELDS: { key: string; label: string }[] = [
  { key: "age",          label: "Age"          },
  { key: "birthday",     label: "Born"         },
  { key: "ethnicity",    label: "Ethnicity"    },
  { key: "height",       label: "Height"       },
  { key: "weight",       label: "Weight"       },
  { key: "measurements", label: "Measurements" },
  { key: "hair",         label: "Hair"         },
  { key: "eyes",         label: "Eyes"         },
  { key: "nationality",  label: "Nationality"  },
  { key: "birthplace",   label: "From"         },
  { key: "years active", label: "Active"       },
  { key: "sexuality",    label: "Sexuality"    },
  { key: "body type",    label: "Body type"    },
]

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

function ModelPhoto({ name, photoUrl, size = 28 }: { name: string; photoUrl?: string; size?: number }) {
  const [failed, setFailed] = useState(false)
  const initials = name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase()).join("")
  const src = photoUrl || buildPhotoUrl(name)

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
      src={src}
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

      <div style={{
        position: "absolute", top: 6, right: 6,
        background: scoreColor(model.opportunity_score),
        color: "#000",
        borderRadius: 10, padding: "1px 6px",
        fontSize: 10, fontWeight: 700, lineHeight: "16px",
      }}>
        {model.opportunity_score}
      </div>

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

// ─── Scene strip (horizontal scroll row) ─────────────────────────────────────

function SceneStrip({ scenes, platform }: {
  scenes: ModelProfile["slr_scenes"]
  platform: "SLR" | "VRP"
}) {
  if (!scenes.length) {
    return (
      <p style={{ fontSize: 11, color: "var(--color-text-faint)", padding: "4px 0" }}>
        No scenes found
      </p>
    )
  }

  return (
    <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
      {scenes.map((scene, i) => (
        <a
          key={i}
          href={scene.url || undefined}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => { if (!scene.url) e.preventDefault() }}
          style={{
            flexShrink: 0,
            width: 140,
            borderRadius: 4,
            overflow: "hidden",
            background: "var(--color-elevated)",
            border: "1px solid var(--color-border-subtle)",
            textDecoration: "none",
            display: "block",
          }}
        >
          {scene.thumb ? (
            <img
              src={scene.thumb}
              alt=""
              aria-hidden="true"
              style={{ width: "100%", height: 78, objectFit: "cover", display: "block" }}
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = "none" }}
            />
          ) : (
            <div style={{
              width: "100%", height: 78,
              background: "var(--color-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ fontSize: 9, color: "var(--color-text-faint)" }}>{platform}</span>
            </div>
          )}
          <div style={{ padding: "5px 6px 6px" }}>
            <div className="line-clamp-2" style={{
              fontSize: 10, fontWeight: 500,
              color: "var(--color-text-muted)",
              lineHeight: 1.35,
            }}>
              {scene.title}
            </div>
            {(scene.date || scene.duration) && (
              <div style={{ fontSize: 9, color: "var(--color-text-faint)", marginTop: 3 }}>
                {[scene.date, scene.duration].filter(Boolean).join(" · ")}
              </div>
            )}
          </div>
        </a>
      ))}
    </div>
  )
}

// ─── Expanded profile panel ───────────────────────────────────────────────────

function ProfilePanel({
  model,
  profile,
  loading,
  onRefresh,
}: {
  model: Model
  profile: ModelProfile | null
  loading: boolean
  onRefresh: () => void
}) {
  const urgency = urgencyLabel(model.last_booked)
  const rankCfg = RANK_CONFIG[model.rank.toLowerCase()]
  const acts = parseActs(model.notes)
  const isActualActList = model.notes.includes(",")

  // Bio fields with values
  const bioRows = BIO_FIELDS
    .map(f => ({ label: f.label, value: profile?.bio[f.key] ?? "" }))
    .filter(r => r.value)

  const hasScrapedData = profile && (
    profile.photo_url || bioRows.length > 0 ||
    profile.slr_scenes.length > 0 || profile.vrp_scenes.length > 0
  )

  return (
    <div style={{
      padding: "14px 12px 16px",
      background: "var(--color-surface)",
      display: "flex", flexDirection: "column", gap: 14,
    }}>

      {/* ── Top row: photo + bio + booking ─────────────────────────────────── */}
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>

        {/* Photo */}
        <div style={{ flexShrink: 0 }}>
          <ModelPhoto
            name={model.name}
            photoUrl={profile?.photo_url || undefined}
            size={88}
          />
        </div>

        {/* Bio facts */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {loading && !profile && (
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 8 }}>
              <div style={{
                width: 12, height: 12, borderRadius: "50%",
                border: "2px solid var(--color-lime)",
                borderTopColor: "transparent",
                animation: "spin 0.7s linear infinite",
              }} />
              <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                Fetching profile…
              </span>
            </div>
          )}

          {bioRows.length > 0 && (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
              gap: "3px 16px",
              marginBottom: 8,
            }}>
              {bioRows.map(r => (
                <div key={r.label} style={{ display: "flex", gap: 4, alignItems: "baseline" }}>
                  <span style={{
                    fontSize: 9, fontWeight: 600, letterSpacing: "0.06em",
                    textTransform: "uppercase", color: "var(--color-text-faint)",
                    flexShrink: 0, whiteSpace: "nowrap",
                  }}>
                    {r.label}
                  </span>
                  <span style={{
                    fontSize: 11, color: "var(--color-text-muted)",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {r.value}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* About */}
          {profile?.bio.about && (
            <p style={{
              fontSize: 11, color: "var(--color-text-faint)",
              lineHeight: 1.5, fontStyle: "italic",
              marginBottom: 8,
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            } as React.CSSProperties}>
              {profile.bio.about}
            </p>
          )}

          {/* Acts (when no scraped data yet) */}
          {!hasScrapedData && isActualActList && acts.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {acts.map(act => (
                <span key={act} style={{
                  fontSize: 10, color: "var(--color-text-muted)",
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: 3, padding: "2px 6px", whiteSpace: "nowrap",
                }}>
                  {act}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Booking history (right column) */}
        <div style={{
          flexShrink: 0, width: 140,
          background: "var(--color-elevated)",
          border: "1px solid var(--color-border-subtle)",
          borderRadius: 5, padding: "8px 10px",
        }}>
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
            textTransform: "uppercase", color: "var(--color-text-faint)",
            marginBottom: 6,
          }}>
            Our bookings
          </div>

          {model.bookings_count && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: "var(--color-text)", lineHeight: 1 }}>
                {model.bookings_count}
              </span>
              <span style={{ fontSize: 10, color: "var(--color-text-faint)", marginLeft: 3 }}>
                total
              </span>
            </div>
          )}

          {model.last_booked && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 9, color: "var(--color-text-faint)" }}>Last</div>
              <div style={{ fontSize: 11, color: urgency.color, fontWeight: 500 }}>
                {model.last_booked}
              </div>
            </div>
          )}

          {profile && Object.keys(profile.booking_studios).length > 0 && (
            <div>
              <div style={{ fontSize: 9, color: "var(--color-text-faint)", marginBottom: 3 }}>
                By studio
              </div>
              {Object.entries(profile.booking_studios).map(([studio, count]) => (
                <div key={studio} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                  <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{studio}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-faint)" }}>{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Scene strips ────────────────────────────────────────────────────── */}
      {(profile?.slr_scenes.length || 0) > 0 && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
              textTransform: "uppercase", color: "var(--color-text-faint)",
            }}>
              SexLikeReal
            </span>
            {profile!.slr_profile_url && (
              <a
                href={profile!.slr_profile_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 9, color: "var(--color-lime)", textDecoration: "none" }}
              >
                Profile ↗
              </a>
            )}
          </div>
          <SceneStrip scenes={profile!.slr_scenes} platform="SLR" />
        </div>
      )}

      {(profile?.vrp_scenes.length || 0) > 0 && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
              textTransform: "uppercase", color: "var(--color-text-faint)",
            }}>
              VRPorn
            </span>
            {profile!.vrp_profile_url && (
              <a
                href={profile!.vrp_profile_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 9, color: "var(--color-lime)", textDecoration: "none" }}
              >
                Profile ↗
              </a>
            )}
          </div>
          <SceneStrip scenes={profile!.vrp_scenes} platform="VRP" />
        </div>
      )}

      {/* ── Footer: cache info + refresh ────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderTop: "1px solid var(--color-border-subtle)", paddingTop: 8,
      }}>
        <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
          {profile?.cached_at
            ? `Cached ${new Date(profile.cached_at).toLocaleDateString()}`
            : loading ? "Fetching…" : "Not yet fetched"}
        </span>
        <button
          onClick={onRefresh}
          disabled={loading}
          style={{
            fontSize: 10, color: loading ? "var(--color-text-faint)" : "var(--color-lime)",
            background: "none", border: "none", cursor: loading ? "default" : "pointer",
            padding: "2px 0",
          }}
        >
          {loading ? "Refreshing…" : "Refresh ↺"}
        </button>
      </div>
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

type SortKey = "score" | "name" | "last_booked" | "rank"

interface Props {
  models: Model[]
  error: string | null
  idToken: string | undefined
}

export function ModelSearch({ models, error, idToken: serverIdToken }: Props) {
  const idToken                               = useIdToken(serverIdToken)
  const [search, setSearch]                  = useState("")
  const [rankFilter, setRankFilter]          = useState("All")
  const [locationFilter, setLocationFilter]  = useState("All")
  const [sortKey, setSortKey]                = useState<SortKey>("score")
  const [expanded, setExpanded]              = useState<string | null>(null)
  const [profiles, setProfiles]              = useState<Record<string, ModelProfile>>({})
  const [loadingProfiles, setLoadingProfiles] = useState<Set<string>>(new Set())
  const deferredSearch                        = useDeferredValue(search)

  const client = useMemo(() => api(idToken ?? null), [idToken])

  const fetchProfile = useCallback(async (name: string, refresh = false) => {
    setLoadingProfiles(prev => new Set(prev).add(name))
    try {
      const data = await client.models.profile(name, refresh)
      setProfiles(prev => ({ ...prev, [name]: data }))
    } catch {
      // silently ignore — profile panel degrades to booking-sheet data only
    } finally {
      setLoadingProfiles(prev => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
    }
  }, [client])

  const handleExpand = useCallback((name: string) => {
    setExpanded(prev => {
      if (prev === name) return null
      // Fetch profile if not already cached
      if (!profiles[name]) {
        fetchProfile(name)
      }
      return name
    })
  }, [profiles, fetchProfile])

  const isFiltered = search !== "" || rankFilter !== "All" || locationFilter !== "All"

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

  return (
    <div>
      {/* ── Spin keyframe (injected once) ─────────────────────────────────────── */}
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>

      {/* ── Top Outreach grid ─────────────────────────────────────────────────── */}
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
                onClick={() => handleExpand(model.name)}
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
            const profile = profiles[model.name] ?? null
            const isLoading = loadingProfiles.has(model.name)

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
                  onClick={() => handleExpand(model.name)}
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
                    <ModelPhoto
                      name={model.name}
                      photoUrl={profile?.photo_url || undefined}
                      size={26}
                    />
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
                        {isLoading && (
                          <div style={{
                            width: 8, height: 8, borderRadius: "50%",
                            border: "1.5px solid var(--color-lime)",
                            borderTopColor: "transparent",
                            animation: "spin 0.7s linear infinite",
                            flexShrink: 0,
                          }} />
                        )}
                      </div>
                      {model.notes && !model.notes.includes(",") && (
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

                {/* Expanded profile panel */}
                {isExpanded && (
                  <div style={{
                    borderBottom: !isLast ? "1px solid var(--color-border-subtle)" : undefined,
                  }}>
                    <ProfilePanel
                      model={model}
                      profile={profile}
                      loading={isLoading}
                      onRefresh={() => fetchProfile(model.name, true)}
                    />
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
