"use client"

import { useState, useMemo, useCallback, useRef } from "react"
import { api, ApiError, API_BASE_URL, type Model, type ModelProfile, type TrendingModel } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"

// ─── Priority outreach (hardcoded) ───────────────────────────────────────────

const PRIORITY: { name: string; agency: string }[] = [
  { name: "Leah Gotti",       agency: "Invision Models"   },
  { name: "Alex Blake",       agency: "Hussie Models"     },
  { name: "Melissa Stratton", agency: "Hussie Models"     },
  { name: "Kenzie Reeves",    agency: "East Coast Talent" },
  { name: "Kali Roses",       agency: "The Model Service" },
  { name: "Haley Reed",       agency: "ATMLA"             },
  { name: "Karma RX",         agency: "ATMLA"             },
  { name: "Cory Chase",       agency: "ATMLA"             },
  { name: "Valentina Nappi",  agency: "Speigler"          },
  { name: "Karlee Grey",      agency: "ATMLA"             },
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(s: number) {
  if (s >= 70) return "var(--color-ok)"
  if (s >= 50) return "var(--color-lime)"
  if (s >= 30) return "var(--color-warn)"
  return "var(--color-text-muted)"
}

/** Server-side photo proxy — bypasses hotlink blocks, tries cache → VRPorn → Babepedia */
function modelPhotoUrl(name: string) {
  return `${API_BASE_URL}/api/models/${encodeURIComponent(name.trim())}/photo`
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase()).join("")
}

const RANK_COLOR: Record<string, string> = {
  great: "var(--color-ok)", good: "var(--color-lime)", moderate: "var(--color-warn)", poor: "var(--color-err)",
}

// ─── Photo component ──────────────────────────────────────────────────────────

function Photo({ src, fallbackSrc, name, width, height, radius = 4, objectPos = "50% 15%" }: {
  src: string; fallbackSrc?: string; name: string; width: number | string; height: number; radius?: number; objectPos?: string
}) {
  const [srcIdx, setSrcIdx] = useState(0)
  const ini = initials(name)
  const srcs = [src, fallbackSrc].filter(Boolean) as string[]
  const activeSrc = srcs[srcIdx]

  if (!activeSrc) {
    return (
      <div style={{
        width, height, borderRadius: radius,
        background: "var(--color-elevated)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: typeof width === "number" ? Math.round(Number(width) * 0.28) : 28,
        fontWeight: 700, color: "var(--color-text-faint)",
        flexShrink: 0,
      }}>
        {ini}
      </div>
    )
  }

  return (
    <img
      src={activeSrc}
      alt=""
      aria-hidden="true"
      referrerPolicy="no-referrer"
      onError={() => setSrcIdx(i => i + 1)}
      style={{
        width, height, borderRadius: radius, flexShrink: 0,
        objectFit: "cover", objectPosition: objectPos, display: "block",
      }}
    />
  )
}

// ─── Model card (trending / priority) ────────────────────────────────────────

function ModelCard({ name, photoSrc, statLine, score, onView }: {
  name: string; photoSrc: string; statLine: string; score?: number; onView: () => void
}) {
  return (
    <div style={{
      borderRadius: 8, overflow: "hidden",
      background: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      display: "flex", flexDirection: "column",
    }}>
      {/* Photo */}
      <div style={{ position: "relative", flexShrink: 0 }}>
        <Photo src={photoSrc} fallbackSrc={modelPhotoUrl(name)} name={name} width="100%" height={180} radius={0} objectPos="50% 15%" />

        {score !== undefined && (
          <div style={{
            position: "absolute", top: 6, right: 6,
            background: scoreColor(score), color: "#000",
            borderRadius: 10, padding: "2px 7px",
            fontSize: 10, fontWeight: 700, lineHeight: "16px",
          }}>
            {score}
          </div>
        )}

        {/* Gradient overlay */}
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0,
          background: "linear-gradient(transparent, rgba(0,0,0,0.85))",
          padding: "28px 8px 8px",
        }}>
          <div style={{
            fontSize: 12, fontWeight: 700, color: "var(--color-text)",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {name}
          </div>
          <div style={{
            fontSize: 10, color: "rgba(255,255,255,0.6)", marginTop: 1,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {statLine}
          </div>
        </div>
      </div>

      {/* View button */}
      <button
        onClick={onView}
        style={{
          background: "var(--color-elevated)",
          border: "none", borderTop: "1px solid var(--color-border-subtle)",
          color: "var(--color-text-muted)",
          fontSize: 11, fontWeight: 500,
          padding: "7px 0", cursor: "pointer", width: "100%",
          transition: "background 0.12s, color 0.12s",
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.background = "var(--color-lime)"
          ;(e.currentTarget as HTMLElement).style.color = "#000"
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.background = "var(--color-elevated)"
          ;(e.currentTarget as HTMLElement).style.color = "var(--color-text-muted)"
        }}
      >
        View
      </button>
    </div>
  )
}

// ─── Scene card ───────────────────────────────────────────────────────────────

function SceneCard({ scene }: { scene: ModelProfile["slr_scenes"][0] }) {
  return (
    <div style={{
      display: "flex", gap: 10,
      padding: "10px 0",
      borderBottom: "1px solid var(--color-border-subtle)",
    }}>
      {/* Thumb */}
      {scene.thumb ? (
        <a href={scene.url || undefined} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0 }}>
          <img
            src={scene.thumb} alt=""
            referrerPolicy="no-referrer"
            crossOrigin="anonymous"
            style={{ width: 120, height: 68, objectFit: "cover", borderRadius: 4, display: "block" }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = "none" }}
          />
        </a>
      ) : (
        <div style={{
          width: 120, height: 68, borderRadius: 4,
          background: "var(--color-elevated)", flexShrink: 0,
        }} />
      )}

      {/* Info */}
      <div style={{ minWidth: 0, flex: 1 }}>
        {scene.url ? (
          <a
            href={scene.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)", textDecoration: "none",
                     display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" } as React.CSSProperties}
          >
            {scene.title}
          </a>
        ) : (
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)" }}>
            {scene.title}
          </div>
        )}

        <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 3 }}>
          {[scene.studio && `🎬 ${scene.studio}`, scene.date && `📅 ${scene.date}`, scene.duration && `⏱ ${scene.duration}`]
            .filter(Boolean).join("  ·  ")}
        </div>
        {(scene.views || scene.likes || scene.comments) && (
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
            {[scene.views && `👁 ${scene.views}`, scene.likes && `❤️ ${scene.likes}`, scene.comments && `💬 ${scene.comments}`]
              .filter(Boolean).join("  ·  ")}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Profile view ─────────────────────────────────────────────────────────────

function ProfileView({ model, profile, loading, profileError, onBack, onRefresh, onBrief, briefText, briefLoading }: {
  model: Model
  profile: ModelProfile | null
  loading: boolean
  profileError: string | null
  onBack: () => void
  onRefresh: () => void
  onBrief: (ctx: Record<string, string>) => void
  briefText: string
  briefLoading: boolean
}) {
  const [briefOpen, setBriefOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<"slr" | "vrp">("slr")

  const sd = model.sheet_data
  const bio = profile?.bio ?? {}
  const bh  = profile?.booking_history

  const rankColor = RANK_COLOR[(model.rank || "").toLowerCase()] || "var(--color-text-faint)"

  // Stats table rows
  const bookingStats = [
    sd["avg rate"] && ["💰 Rate", sd["avg rate"]],
    model.bookings_count && ["📋 Bookings", model.bookings_count],
    model.last_booked && ["📅 Last Booked", model.last_booked],
    model.location && ["📍 Location", model.location],
    sd["status"] && ["✅ Status", sd["status"]],
  ].filter(Boolean) as [string, string][]

  const platformStats = [
    sd["slr followers"] && ["👥 SLR Followers", sd["slr followers"]],
    sd["slr scenes"]    && ["🎬 SLR Scenes",    sd["slr scenes"]],
    sd["slr views"]     && ["👁 SLR Views",      sd["slr views"]],
    sd["vrp followers"] && ["👥 VRP Followers",  sd["vrp followers"]],
    sd["vrp views"]     && ["👁 VRP Views",       sd["vrp views"]],
    sd["povr views"]    && ["👁 POVR Views",      sd["povr views"]],
  ].filter(Boolean) as [string, string][]

  const socialStats = [
    sd["onlyfans"]  && ["🔞 OnlyFans",  sd["onlyfans"]],
    sd["twitter"]   && ["𝕏 Twitter",    sd["twitter"]],
    sd["instagram"] && ["📸 Instagram", sd["instagram"]],
  ].filter(Boolean) as [string, string][]

  const BIO_KEYS: [string | null, string | null, string][] = [
    [null,             "birthday",    "Born"],
    [null,             "birthplace",  "Birthplace"],
    [null,             "nationality", "Nationality"],
    [null,             "ethnicity",   "Ethnicity"],
    ["height",         "height",      "Height"],
    ["weight",         "weight",      "Weight"],
    ["measurements",   "measurements","Measurements"],
    [null,             "bra/cup size","Bra / Cup"],
    ["hair",           "hair",        "Hair"],
    ["eyes",           "eyes",        "Eyes"],
    [null,             "years active","Years Active"],
  ]
  const physStats = BIO_KEYS.map(([bk, bk2, label]) => {
    const val = (bk ? sd[bk] : "") || (bk2 ? bio[bk2] : "")
    return val ? [label, val] as [string, string] : null
  }).filter(Boolean) as [string, string][]

  // Competitor activity
  const ourStudios = new Set(["fuckpassvr","vrhush","vrallure","blowjobnow","fpvr","vr hush","njoi","naughty joi"])
  const allScenes = [...(profile?.slr_scenes ?? []), ...(profile?.vrp_scenes ?? [])]
  const competitors: { studio: string; title: string; date: string }[] = []
  const seenStud: Record<string, { studio: string; title: string; date: string }> = {}
  for (const sc of allScenes) {
    const sk = (sc.studio || "").toLowerCase().replace(/\s/g, "")
    if (!sc.studio || ourStudios.has(sk)) continue
    if (!seenStud[sc.studio] || sc.date > seenStud[sc.studio].date)
      seenStud[sc.studio] = { studio: sc.studio, title: sc.title, date: sc.date }
  }
  Object.values(seenStud).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8).forEach(c => competitors.push(c))

  function StatTable({ rows, title }: { rows: [string, string][]; title?: string }) {
    if (!rows.length) return null
    return (
      <>
        {title && (
          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
                        textTransform: "uppercase", color: "var(--color-text-faint)",
                        marginTop: 10, marginBottom: 3 }}>
            {title}
          </div>
        )}
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label}>
                <td style={{ fontSize: 11, color: "var(--color-text-faint)", padding: "3px 10px 3px 0", whiteSpace: "nowrap" }}>
                  {label}
                </td>
                <td style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)" }}>
                  {value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    )
  }

  function buildBriefCtx(): Record<string, string> {
    const ctx: Record<string, string> = {}
    if (model.rank) ctx["Booking rank"] = model.rank
    if (model.agency) ctx["Agency"] = model.agency
    if (sd["slr followers"]) ctx["SLR followers"] = sd["slr followers"]
    if (sd["slr scenes"]) ctx["SLR scenes"] = sd["slr scenes"]
    if (sd["vrp followers"]) ctx["VRP followers"] = sd["vrp followers"]
    if (sd["vrp views"]) ctx["VRPorn views"] = sd["vrp views"]
    if (sd["available for"]) ctx["Available for"] = sd["available for"]
    if (model.rate) ctx["Rate"] = model.rate
    if (bh?.total) ctx["Booked with our studio"] = `${bh.total} times`
    if (bh?.last_display) ctx["Last booked"] = bh.last_display
    if (model.last_booked && !bh?.total) ctx["Never booked with your studio"] = "true"
    return ctx
  }

  const slr = profile?.slr_scenes ?? []
  const vrp = profile?.vrp_scenes ?? []

  return (
    <div>
      {/* ── Back + Refresh ───────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <button
          onClick={onBack}
          style={{ fontSize: 12, color: "var(--color-lime)", background: "none", border: "none",
                   cursor: "pointer", padding: 0 }}
        >
          ← Back to list
        </button>
        <button
          onClick={onRefresh}
          disabled={loading}
          style={{ fontSize: 11, color: loading ? "var(--color-text-faint)" : "var(--color-text-muted)",
                   background: "none", border: "none", cursor: loading ? "default" : "pointer", padding: 0 }}
        >
          {loading ? "Refreshing…" : "🔄 Refresh"}
        </button>
      </div>

      {/* ── Profile load error ──────────────────────────────────────────────── */}
      {profileError && !loading && (
        <div style={{
          marginBottom: 12,
          padding: "8px 12px",
          borderRadius: 6,
          background: "color-mix(in srgb, var(--color-err) 10%, transparent)",
          border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
          fontSize: 12,
          color: "var(--color-err)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}>
          <span>{profileError}</span>
          <button
            onClick={onRefresh}
            style={{ fontSize: 11, color: "var(--color-err)", background: "none", border: "none",
                     cursor: "pointer", padding: 0, opacity: 0.8, flexShrink: 0 }}
          >
            Retry ↺
          </button>
        </div>
      )}

      {/* ── Header: photo | info | booking history ───────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "140px 1fr 200px", gap: 20, marginBottom: 16 }}>

        {/* Photo */}
        <div>
          <Photo
            src={profile?.photo_url || ""}
            fallbackSrc={modelPhotoUrl(model.name)}
            name={model.name}
            width={140}
            height={190}
            radius={6}
            objectPos="50% 10%"
          />
        </div>

        {/* Info column */}
        <div>
          {/* Name + age + rank */}
          <div className="flex items-baseline gap-2 flex-wrap" style={{ marginBottom: 6 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text)", lineHeight: 1.2 }}>
              {model.name}
            </span>
            {model.age && (
              <span style={{ fontSize: 14, color: "var(--color-text-muted)" }}>{model.age}</span>
            )}
            {model.rank && (
              <span style={{
                fontSize: 11, fontWeight: 600, color: rankColor,
                background: `color-mix(in srgb, ${rankColor} 12%, transparent)`,
                border: `1px solid color-mix(in srgb, ${rankColor} 25%, transparent)`,
                borderRadius: 4, padding: "2px 7px",
              }}>
                {model.rank.charAt(0).toUpperCase() + model.rank.slice(1).toLowerCase()}
              </span>
            )}
          </div>

          {/* Agency + profile links */}
          <div style={{ fontSize: 12, marginBottom: 6 }}>
            {model.agency_link ? (
              <a href={model.agency_link} target="_blank" rel="noopener noreferrer"
                style={{ color: "var(--color-lime)", textDecoration: "none" }}>
                {model.agency || "Agency"}
              </a>
            ) : (
              <span style={{ color: "var(--color-text-muted)" }}>
                {model.agency || <em style={{ color: "var(--color-text-faint)" }}>Not in booking sheet</em>}
              </span>
            )}
            {profile?.slr_profile_url && (
              <a href={profile.slr_profile_url} target="_blank" rel="noopener noreferrer"
                style={{ marginLeft: 12, fontSize: 11, color: "var(--color-text-faint)", textDecoration: "none" }}>
                SLR ↗
              </a>
            )}
            {profile?.vrp_profile_url && (
              <a href={profile.vrp_profile_url} target="_blank" rel="noopener noreferrer"
                style={{ marginLeft: 8, fontSize: 11, color: "var(--color-text-faint)", textDecoration: "none" }}>
                VRPorn ↗
              </a>
            )}
          </div>

          {/* Rate · status · location */}
          {[model.rate && `💰 ${model.rate}`, sd["status"], model.location && `📍 ${model.location}`]
            .filter(Boolean).length > 0 && (
            <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginBottom: 8 }}>
              {[model.rate && `💰 ${model.rate}`, sd["status"], model.location && `📍 ${model.location}`]
                .filter(Boolean).join("  ·  ")}
            </div>
          )}

          {/* Available For tags */}
          {(sd["available for"] || model.notes) && (
            <div className="flex flex-wrap gap-1">
              {((sd["available for"] || model.notes) ?? "").split(",").map(t => t.trim()).filter(Boolean).map(tag => (
                <span key={tag} style={{
                  fontSize: 10, color: "var(--color-text-muted)",
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: 3, padding: "2px 6px",
                }}>
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Notes warning */}
          {sd["notes"] && (
            <div style={{
              marginTop: 8, padding: "6px 10px", borderRadius: 4,
              background: "color-mix(in srgb, var(--color-warn) 10%, transparent)",
              border: "1px solid color-mix(in srgb, var(--color-warn) 25%, transparent)",
              fontSize: 11, color: "var(--color-warn)",
            }}>
              ⚠️ {sd["notes"]}
            </div>
          )}
        </div>

        {/* Booking history card */}
        <div style={{
          background: bh?.total
            ? "color-mix(in srgb, var(--color-ok) 8%, transparent)"
            : "color-mix(in srgb, var(--color-err) 8%, transparent)",
          border: `1px solid color-mix(in srgb, ${bh?.total ? "var(--color-ok)" : "var(--color-err)"} 20%, transparent)`,
          borderRadius: 8, padding: "12px 14px",
        }}>
          {bh?.total ? (
            <>
              <div style={{ color: "var(--color-ok)", fontSize: 20, fontWeight: 700, lineHeight: 1 }}>
                {bh.total}× booked
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6 }}>
                Last: {bh.last_display || bh.last_date}
              </div>
              {model.rate && (
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>
                  Rate: {model.rate}
                </div>
              )}
              {bh.studios && Object.keys(bh.studios).length > 0 && (
                <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 6 }}>
                  {Object.entries(bh.studios)
                    .sort(([, a], [, b]) => b - a)
                    .map(([s, n]) => `${s} (${n}×)`)
                    .join(" · ")}
                </div>
              )}
            </>
          ) : (
            <div style={{ color: "var(--color-err)", fontSize: 12 }}>
              🔴 Never booked with your studio
            </div>
          )}
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--color-border)", marginBottom: 16 }} />

      {/* ── AI Booking Brief ─────────────────────────────────────────────────── */}
      <div style={{
        marginBottom: 16,
        border: "1px solid var(--color-border)",
        borderRadius: 6, overflow: "hidden",
      }}>
        <button
          onClick={() => setBriefOpen(o => !o)}
          style={{
            width: "100%", textAlign: "left",
            padding: "8px 12px",
            background: briefOpen ? "var(--color-elevated)" : "var(--color-surface)",
            border: "none", cursor: "pointer",
            fontSize: 12, color: "var(--color-text-muted)",
            display: "flex", alignItems: "center", gap: 6,
          }}
        >
          <span style={{ color: "var(--color-lime)" }}>✦</span>
          Generate Booking Brief
          <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-text-faint)" }}>
            {briefOpen ? "▲" : "▼"}
          </span>
        </button>

        {briefOpen && (
          <div style={{ padding: "10px 12px", background: "var(--color-surface)" }}>
            <button
              onClick={() => onBrief(buildBriefCtx())}
              disabled={briefLoading}
              style={{
                fontSize: 11, padding: "5px 12px", borderRadius: 4,
                background: briefLoading ? "var(--color-elevated)" : "var(--color-lime)",
                color: briefLoading ? "var(--color-text-faint)" : "#000",
                border: "none", cursor: briefLoading ? "default" : "pointer", fontWeight: 600,
              }}
            >
              {briefLoading ? "Generating…" : "Generate"}
            </button>

            {briefText && (
              <div style={{
                marginTop: 10, fontSize: 12, lineHeight: 1.65,
                color: "var(--color-text)", padding: "10px 12px",
                background: "var(--color-elevated)", borderRadius: 4,
              }}>
                {briefText}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Two-column body ──────────────────────────────────────────────────── */}
      {loading && !profile && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
          <div style={{
            width: 12, height: 12, borderRadius: "50%",
            border: "2px solid var(--color-lime)",
            borderTopColor: "transparent",
            animation: "spin 0.7s linear infinite",
          }} />
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>Fetching profile data…</span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "5fr 7fr", gap: 24, alignItems: "start" }}>

        {/* ── Left: stats + bio ──────────────────────────────────────────────── */}
        <div>
          <StatTable rows={bookingStats} />
          {platformStats.length > 0 && <StatTable rows={platformStats} title="Platform" />}
          {socialStats.length > 0 && <StatTable rows={socialStats} title="Social" />}

          {physStats.length > 0 && (
            <>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
                            textTransform: "uppercase", color: "var(--color-text-faint)",
                            marginTop: 12, marginBottom: 3 }}>
                Physical Stats
              </div>
              <StatTable rows={physStats} />
            </>
          )}

          {bio["about"] && (
            <p style={{
              fontSize: 12, color: "var(--color-text)", lineHeight: 1.55,
              marginTop: 10, fontStyle: "italic",
            }}>
              {bio["about"]}
            </p>
          )}

          {/* Competitor activity */}
          {competitors.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
                            textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
                Competitor Activity
              </div>
              {competitors.map((c, i) => (
                <div key={i} style={{ fontSize: 11, color: "var(--color-text-faint)", marginBottom: 3 }}>
                  <span style={{ fontWeight: 600, color: "var(--color-text-muted)" }}>{c.studio}</span>
                  {c.date && ` · ${c.date}`}
                  {c.title && ` — `}
                  {c.title && <em>{c.title.slice(0, 50)}</em>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Right: scene tabs ──────────────────────────────────────────────── */}
        <div>
          {/* Tab bar */}
          <div className="flex gap-1 mb-3">
            {(["slr", "vrp"] as const).map(tab => {
              const count = tab === "slr" ? slr.length : vrp.length
              const label = tab === "slr" ? `SexLikeReal${count ? ` (${count})` : ""}` : `VRPorn${count ? ` (${count})` : ""}`
              const active = activeTab === tab
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className="px-3 py-1 rounded text-xs transition-colors"
                  style={{
                    fontWeight: active ? 600 : 400,
                    color: active ? "var(--color-text)" : "var(--color-text-faint)",
                    background: active ? "color-mix(in srgb, var(--color-lime) 10%, transparent)" : "transparent",
                    border: `1px solid ${active ? "color-mix(in srgb, var(--color-lime) 25%, transparent)" : "transparent"}`,
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>

          <div style={{ paddingTop: 4 }}>
            {activeTab === "slr" && (
              slr.length
                ? <>
                    {slr.slice(0, 6).map((sc, i) => <SceneCard key={i} scene={sc} />)}
                    {slr.length > 6 && (
                      <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 6 }}>
                        Showing 6 of {slr.length} scenes
                      </p>
                    )}
                  </>
                : <p style={{ fontSize: 12, color: "var(--color-text-faint)", padding: "12px 0" }}>
                    {loading ? "Loading…" : "No SLR scenes found."}
                  </p>
            )}
            {activeTab === "vrp" && (
              vrp.length
                ? <>
                    {vrp.slice(0, 6).map((sc, i) => <SceneCard key={i} scene={sc} />)}
                    {vrp.length > 6 && (
                      <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 6 }}>
                        Showing 6 of {vrp.length} scenes
                      </p>
                    )}
                  </>
                : <p style={{ fontSize: 12, color: "var(--color-text-faint)", padding: "12px 0" }}>
                    {loading ? "Loading…" : "No VRPorn scenes found."}
                  </p>
            )}
          </div>

          {profile?.cached_at && (
            <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 10 }}>
              Cached {new Date(profile.cached_at).toLocaleDateString()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  models: Model[]
  error: string | null
  idToken: string | undefined
}

export function ModelSearch({ models, error, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const client  = useMemo(() => api(idToken ?? null), [idToken])

  const [searchInput, setSearchInput]     = useState("")
  const [currentModel, setCurrentModel]   = useState<Model | null>(null)
  const [profile, setProfile]             = useState<ModelProfile | null>(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError]   = useState<string | null>(null)
  const [trending, setTrending]           = useState<TrendingModel[] | null>(null)
  const [trendingLoading, setTrendingLoading] = useState(false)
  const [trendingLoaded, setTrendingLoaded] = useState(false)
  const [briefText, setBriefText]         = useState("")
  const [briefLoading, setBriefLoading]   = useState(false)

  // Load trending on first render
  const loadTrending = useCallback(async (refresh = false) => {
    setTrendingLoading(true)
    try {
      const data = await client.models.trending(10, refresh)
      setTrending(data)
    } catch {
      setTrending([])
    } finally {
      setTrendingLoading(false)
      setTrendingLoaded(true)
    }
  }, [client])

  // Lazy-load trending when default view first renders
  const hasFetchedTrending = useRef(false)
  if (!hasFetchedTrending.current && !currentModel) {
    hasFetchedTrending.current = true
    loadTrending()
  }

  const openProfile = useCallback(async (name: string, refresh = false) => {
    const m = models.find(mo => mo.name.toLowerCase() === name.toLowerCase())
      ?? { name, agency: "", agency_link: "", rate: "", rank: "", notes: "",
           info: "", age: "", last_booked: "", bookings_count: "", location: "",
           opportunity_score: 0, sheet_data: {} }

    setCurrentModel(m)
    setProfile(null)
    setProfileError(null)
    setBriefText("")
    setProfileLoading(true)

    try {
      const data = await client.models.profile(name, refresh)
      setProfile(data)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setProfileError("Session expired — please refresh the page or sign in again.")
      } else if (e instanceof ApiError && e.status === 404) {
        setProfileError("Profile not found for this model.")
      } else {
        setProfileError("Failed to load profile data.")
      }
    } finally {
      setProfileLoading(false)
    }
  }, [models, client])

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    const q = searchInput.trim()
    if (!q) return
    openProfile(q)
  }, [searchInput, openProfile])

  const handleBrief = useCallback(async (ctx: Record<string, string>) => {
    if (!currentModel) return
    setBriefLoading(true)
    try {
      const res = await client.models.brief(currentModel.name, ctx)
      setBriefText(res.brief)
    } catch {
      setBriefText("Could not generate brief — check API key.")
    } finally {
      setBriefLoading(false)
    }
  }, [currentModel, client])

  // Opportunity score for a name based on booking list
  const scoreFor = useCallback((name: string) => {
    const m = models.find(mo => mo.name.toLowerCase() === name.toLowerCase())
    return m?.opportunity_score
  }, [models])

  // ── Profile view ───────────────────────────────────────────────────────────
  if (currentModel) {
    return (
      <>

        <ProfileView
          model={currentModel}
          profile={profile}
          loading={profileLoading}
          profileError={profileError}
          onBack={() => { setCurrentModel(null); setProfile(null); setProfileError(null) }}
          onRefresh={() => openProfile(currentModel.name, true)}
          onBrief={handleBrief}
          briefText={briefText}
          briefLoading={briefLoading}
        />
      </>
    )
  }

  // ── Default view: search + trending + priority ─────────────────────────────

  // Priority cards: find photo from trending list or babepedia guess
  const trendingPhotoMap = useMemo(() => {
    const map: Record<string, string> = {}
    trending?.forEach(t => { map[t.name.toLowerCase()] = t.photo_url })
    return map
  }, [trending])

  return (
    <div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>

      {/* ── Search bar ─────────────────────────────────────────────────────── */}
      <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          type="text"
          placeholder="Search any performer…"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          style={{
            flex: 1, padding: "8px 12px", borderRadius: 4, fontSize: 13,
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text)", outline: "none",
          }}
        />
        <button
          type="submit"
          style={{
            padding: "8px 18px", borderRadius: 4, fontSize: 13, fontWeight: 600,
            background: "var(--color-lime)", color: "#000", border: "none", cursor: "pointer",
          }}
        >
          Search
        </button>
      </form>

      {/* ── Trending Now ───────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
          textTransform: "uppercase", color: "var(--color-njoi)",
        }}>
          🔥 Trending Now
        </span>
        <button
          onClick={() => loadTrending(true)}
          disabled={trendingLoading}
          style={{
            fontSize: 11, background: "none", border: "none",
            color: trendingLoading ? "var(--color-text-faint)" : "var(--color-text-muted)",
            cursor: trendingLoading ? "default" : "pointer", padding: 0,
          }}
        >
          {trendingLoading ? "Loading…" : "↺"}
        </button>
      </div>

      {trendingLoading && !trending && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 20, paddingTop: 4 }}>
          <div style={{
            width: 11, height: 11, borderRadius: "50%",
            border: "2px solid var(--color-njoi)", borderTopColor: "transparent",
            animation: "spin 0.7s linear infinite",
          }} />
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>Loading trending models…</span>
        </div>
      )}

      {trending && trending.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginBottom: 24 }}>
          {trending.slice(0, 10).map(t => (
            <ModelCard
              key={t.name}
              name={t.name}
              photoSrc={t.photo_url}
              statLine={[t.platform, t.scenes ? `${t.scenes} scenes` : "", t.followers].filter(Boolean).join(" · ")}
              score={scoreFor(t.name)}
              onView={() => openProfile(t.name)}
            />
          ))}
        </div>
      )}

      {trendingLoaded && (!trending || trending.length === 0) && (
        <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginBottom: 20 }}>
          Could not load trending models — check connection or click ↺.
        </p>
      )}

      {/* ── Priority Outreach ──────────────────────────────────────────────── */}
      <div style={{ marginBottom: 10 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
          textTransform: "uppercase", color: "var(--color-ok)",
        }}>
          ⭐ Priority Outreach
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
        {PRIORITY.map(p => {
          const m = models.find(mo => mo.name.toLowerCase() === p.name.toLowerCase())
          const score = m?.opportunity_score
          const photo = trendingPhotoMap[p.name.toLowerCase()] || modelPhotoUrl(p.name)
          const statLine = m
            ? [p.agency, m.last_booked ? `Last: ${m.last_booked}` : "Never booked"].join(" · ")
            : [p.agency, "Never booked"].join(" · ")
          return (
            <ModelCard
              key={p.name}
              name={p.name}
              photoSrc={photo}
              statLine={statLine}
              score={score}
              onView={() => openProfile(p.name)}
            />
          )
        })}
      </div>

      {error && (
        <p style={{ fontSize: 12, color: "var(--color-err)", marginTop: 16 }}>{error}</p>
      )}
    </div>
  )
}
