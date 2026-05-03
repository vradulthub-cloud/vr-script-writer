"use client"

import { useState, useMemo, useCallback, useRef, useEffect } from "react"
import { api, ApiError, type Model, type ModelProfile, type TrendingModel } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { PageHeader } from "@/components/ui/page-header"
import { TableSkeleton } from "@/components/ui/skeleton"
import { modelPhotoUrl } from "./model-utils"
import { ModelCard } from "./model-card"
import { ProfileView } from "./profile-view"

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
  const [trendingCount, setTrendingCount] = useState(10)
  const [briefText, setBriefText]         = useState("")
  const [briefLoading, setBriefLoading]   = useState(false)

  // Load trending on first render
  const loadTrending = useCallback(async (refresh = false, count = trendingCount) => {
    setTrendingLoading(true)
    try {
      const data = await client.models.trending(count, refresh)
      setTrending(data)
    } catch {
      setTrending([])
    } finally {
      setTrendingLoading(false)
      setTrendingLoaded(true)
    }
  }, [client, trendingCount])

  // Lazy-load trending when default view first renders
  const hasFetchedTrending = useRef(false)
  useEffect(() => {
    if (hasFetchedTrending.current || currentModel) return
    hasFetchedTrending.current = true
    loadTrending()
    // loadTrending depends on client/count — intentionally fire once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
      // Refetch the individual model alongside the profile so agency
      // changes in the booking sheet land in-session without a reload.
      // The cached list can be minutes or hours stale.
      const [data, fresh] = await Promise.all([
        client.models.profile(name, refresh),
        client.models.get(name).catch(() => null),
      ])
      if (fresh) setCurrentModel(fresh)
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

  // Priority cards: find photo from trending list or babepedia guess
  // NOTE: must be declared BEFORE any conditional return — violating that
  // breaks the Rules of Hooks (React error #300: rendered fewer hooks)
  const trendingPhotoMap = useMemo(() => {
    const map: Record<string, string> = {}
    trending?.forEach(t => { map[t.name.toLowerCase()] = t.photo_url })
    return map
  }, [trending])

  const handleClearCache = useCallback(async () => {
    if (!currentModel) return
    try {
      await client.models.clearCache(currentModel.name)
    } catch {
      // Non-critical — proceed to refresh anyway
    }
    openProfile(currentModel.name, true)
  }, [currentModel, client, openProfile])

  // ── Profile view ───────────────────────────────────────────────────────────
  if (currentModel) {
    return (
      <ProfileView
        model={currentModel}
        profile={profile}
        loading={profileLoading}
        profileError={profileError}
        onBack={() => { setCurrentModel(null); setProfile(null); setProfileError(null) }}
        onRefresh={() => openProfile(currentModel.name, true)}
        onClearCache={handleClearCache}
        onBrief={handleBrief}
        briefText={briefText}
        briefLoading={briefLoading}
      />
    )
  }

  // ── Default view: search + trending + priority ─────────────────────────────
  return (
    <div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>

      <PageHeader
        title="Model Research"
        eyebrow="Booking intel"
        subtitle={
          trending
            ? `${trending.length.toLocaleString()} trending · ${PRIORITY.length.toLocaleString()} priority outreach`
            : undefined
        }
        actions={
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 8 }}>
            <input
              type="text"
              aria-label="Search performers"
              placeholder="Search any performer…"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              style={{
                width: 280, padding: "7px 12px", borderRadius: 4, fontSize: 13,
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)", outline: "none",
              }}
            />
            <button
              type="submit"
              style={{
                padding: "7px 14px", borderRadius: 4, fontSize: 12, fontWeight: 600,
                background: "var(--color-lime)", color: "#000", border: "none", cursor: "pointer",
              }}
            >
              Search
            </button>
          </form>
        }
      />

      {/* ── Trending Now ───────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
          textTransform: "uppercase", color: "var(--color-njoi)",
        }}>
          Trending Now
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
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2 mb-2">
            {trending.map(t => {
              const m = models.find(mo => mo.name.toLowerCase() === t.name.toLowerCase())
              return (
                <ModelCard
                  key={t.name}
                  name={t.name}
                  photoSrc={t.photo_url}
                  statLine={[t.platform, t.scenes ? `${t.scenes} scenes` : "", t.followers].filter(Boolean).join(" · ")}
                  score={scoreFor(t.name)}
                  rank={m?.rank}
                  bookings={m?.bookings_count}
                  onView={() => openProfile(t.name)}
                />
              )
            })}
          </div>
          {trending.length >= trendingCount && (
            <button
              onClick={() => {
                const next = trendingCount + 10
                setTrendingCount(next)
                void loadTrending(false, next)
              }}
              disabled={trendingLoading}
              style={{
                fontSize: 11, color: "var(--color-text-muted)", background: "none", border: "none",
                cursor: trendingLoading ? "default" : "pointer", marginBottom: 16, padding: "4px 0",
              }}
            >
              {trendingLoading ? "Loading…" : `Show more ↓`}
            </button>
          )}
        </>
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
          Priority Outreach
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
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
              rank={m?.rank}
              bookings={m?.bookings_count}
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
