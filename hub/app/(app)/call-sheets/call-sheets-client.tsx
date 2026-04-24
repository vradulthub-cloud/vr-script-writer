"use client"

import { useState, useEffect, useMemo, useRef } from "react"
import { api } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { PageHeader } from "@/components/ui/page-header"
import { SkeletonBar } from "@/components/ui/skeleton"
import { STUDIO_COLOR, STUDIO_ABBR } from "@/lib/studio-colors"
import type { ShootDate } from "@/lib/api"

// ---------------------------------------------------------------------------
// DateCard — Variant B (card grid with scenes always visible)
// ---------------------------------------------------------------------------

interface DateCardProps {
  date: ShootDate
  doorCode: string
  idToken: string | undefined
  tabName: string
  batchResult?: { url?: string; error?: string }
}

function DateCard({ date, doorCode, idToken, tabName, batchResult }: DateCardProps) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ url: string; title: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [justGenerated, setJustGenerated] = useState(false)
  const prevBatchResult = useRef(batchResult)

  // Flash border when batch completes this card
  useEffect(() => {
    if (batchResult && batchResult !== prevBatchResult.current) {
      prevBatchResult.current = batchResult
      if (batchResult.url) {
        setJustGenerated(true)
        setTimeout(() => setJustGenerated(false), 1500)
      }
    }
  }, [batchResult])

  async function generate(e?: React.MouseEvent) {
    e?.stopPropagation()
    setLoading(true)
    setError(null)
    try {
      const data = await api(idToken ?? null).callSheets.generate({
        date_key: date.date_key,
        door_code: doorCode,
        tab_name: tabName || undefined,
      })
      setResult({ url: data.doc_url, title: data.title })
      setJustGenerated(true)
      setTimeout(() => setJustGenerated(false), 1500)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed")
    } finally {
      setLoading(false)
    }
  }

  const uniqueStudios = [...new Set(date.scenes.map(s => s.studio))]
  const generated = result !== null || !!batchResult?.url
  const effectiveUrl = result?.url ?? batchResult?.url

  // "Apr 25" → day number "25", weekday from date_display "Fri, Apr 25" → "Fri"
  const parts = date.date_display.split(", ")
  const weekday = parts[0] ?? ""
  const dayNum = parts[1]?.split(" ")[1] ?? date.date_display

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        overflow: "hidden",
        boxShadow: justGenerated ? "inset 0 0 0 1px var(--color-ok)" : "none",
        transition: "box-shadow 0.3s",
      }}
    >
      {/* Card header — day number + weekday/scenes + studio chips */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid var(--color-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontWeight: 800,
              fontSize: 24,
              lineHeight: 1,
              letterSpacing: "-0.02em",
              color: "var(--color-text)",
            }}
          >
            {dayNum}
          </span>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text)" }}>{weekday}</div>
            <div style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
              {date.scenes.length} scene{date.scenes.length !== 1 ? "s" : ""}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {uniqueStudios.map(s => {
            const color = STUDIO_COLOR[s] ?? "var(--color-text-muted)"
            const abbr = STUDIO_ABBR[s] ?? s
            return (
              <span
                key={s}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "2px 6px",
                  border: `1px solid ${color}`,
                  fontFamily: "var(--font-mono)",
                  fontSize: 9,
                  fontWeight: 800,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color,
                }}
              >
                {abbr}
              </span>
            )
          })}
        </div>
      </div>

      {/* Scene rows */}
      <div>
        {date.scenes.map((sc, i) => {
          const color = STUDIO_COLOR[sc.studio] ?? "var(--color-text-muted)"
          const secondary = [sc.type, sc.male, sc.agency].filter(Boolean).join(" · ")
          return (
            <div
              key={i}
              style={{
                padding: "10px 16px",
                borderBottom: i < date.scenes.length - 1 ? "1px solid var(--color-border-subtle)" : "none",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span style={{ width: 3, height: 28, background: color, flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)" }}>
                  {sc.female || "—"}
                </div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{secondary}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Error */}
      {(error || batchResult?.error) && (
        <div style={{ padding: "0 16px 8px" }}>
          <ErrorAlert className="text-xs">{error ?? batchResult?.error}</ErrorAlert>
        </div>
      )}

      {/* Actions footer */}
      <div
        style={{
          padding: "10px 16px",
          borderTop: "1px solid var(--color-border)",
          display: "flex",
          gap: 8,
          justifyContent: "flex-end",
          background: "var(--color-base)",
        }}
      >
        {generated && effectiveUrl && (
          <a
            href={effectiveUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: 10,
              fontWeight: 600,
              padding: "5px 12px",
              background: "color-mix(in srgb, var(--color-ok) 12%, transparent)",
              border: "1px solid color-mix(in srgb, var(--color-ok) 28%, transparent)",
              color: "var(--color-ok)",
              textDecoration: "none",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            Open ↗
          </a>
        )}
        <button
          onClick={generate}
          disabled={loading}
          style={{
            padding: "5px 14px",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            background: loading ? "var(--color-elevated)" : "var(--color-lime)",
            color: loading ? "var(--color-text-muted)" : "var(--color-lime-ink)",
            border: `1px solid ${loading ? "var(--color-border)" : "var(--color-lime)"}`,
            cursor: loading ? "wait" : "pointer",
          }}
        >
          {loading ? "Generating…" : generated ? "Regenerate" : "Generate"}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// TabSelector
// ---------------------------------------------------------------------------

function TabSelector({
  tabs,
  active,
  onChange,
  disabled,
}: {
  tabs: string[]
  active: string
  onChange: (tab: string) => void
  disabled?: boolean
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "stretch",
        border: "1px solid var(--color-border)",
        background: "var(--color-surface)",
        width: "fit-content",
      }}
    >
      {tabs.map((tab, i) => (
        <button
          key={tab}
          disabled={disabled}
          onClick={() => onChange(tab)}
          style={{
            padding: "8px 14px",
            background: active === tab ? "var(--color-text)" : "transparent",
            border: "none",
            borderRight: i < tabs.length - 1 ? "1px solid var(--color-border)" : "none",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: active === tab ? "var(--color-base)" : "var(--color-text-muted)",
            cursor: disabled ? "wait" : "pointer",
          }}
        >
          {tab}
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------

export function CallSheetsClient({
  idToken: serverIdToken,
  initialTabs = [],
  initialTabsError = null,
}: {
  idToken?: string
  initialTabs?: string[]
  initialTabsError?: string | null
} = {}) {
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [tabs, setTabs] = useState<string[]>(initialTabs)
  const [activeTab, setActiveTab] = useState<string>(initialTabs[0] ?? "")
  const [dates, setDates] = useState<ShootDate[]>([])
  const [doorCode, setDoorCode] = useState("1322")
  const [showDoorCode, setShowDoorCode] = useState(false)
  const [tabsLoading, setTabsLoading] = useState(initialTabs.length === 0 && !initialTabsError)
  const [datesLoading, setDatesLoading] = useState(false)
  const [tabsError, setTabsError] = useState<string | null>(initialTabsError)
  const [datesError, setDatesError] = useState<string | null>(null)

  // Batch state — keyed by date_key
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchProgress, setBatchProgress] = useState(0)
  const [batchTotal, setBatchTotal] = useState(0)
  const [batchResults, setBatchResults] = useState<Record<string, { url?: string; error?: string }>>({})
  const [batchDone, setBatchDone] = useState(false)
  const [batchCurrentDate, setBatchCurrentDate] = useState<string | null>(null)

  async function generateAll() {
    if (dates.length === 0 || batchRunning) return
    setBatchRunning(true)
    setBatchDone(false)
    setBatchTotal(dates.length)
    setBatchProgress(0)
    setBatchResults({})

    for (let i = 0; i < dates.length; i++) {
      const d = dates[i]
      setBatchCurrentDate(d.date_display)
      setBatchProgress(i + 1)
      try {
        const data = await client.callSheets.generate({
          date_key: d.date_key,
          door_code: doorCode,
          tab_name: activeTab || undefined,
        })
        setBatchResults(prev => ({ ...prev, [d.date_key]: { url: data.doc_url } }))
      } catch (e) {
        setBatchResults(prev => ({
          ...prev,
          [d.date_key]: { error: e instanceof Error ? e.message : "Failed" },
        }))
      }
    }
    setBatchRunning(false)
    setBatchDone(true)
    setBatchCurrentDate(null)
  }

  useEffect(() => {
    if (tabs.length > 0 || tabsError) return
    setTabsLoading(true)
    client.callSheets.tabs()
      .then(data => {
        setTabs(data)
        if (data.length > 0) setActiveTab(data[0])
        setTabsLoading(false)
      })
      .catch(e => {
        setTabsError(e instanceof Error ? e.message : "Could not load tabs")
        setTabsLoading(false)
      })
  }, [tabs.length, tabsError, client])

  useEffect(() => {
    if (!activeTab) return
    setDatesLoading(true)
    setDatesError(null)
    setDates([])
    setBatchResults({})
    setBatchDone(false)
    client.callSheets.dates(activeTab)
      .then(data => {
        setDates(data)
        setDatesLoading(false)
      })
      .catch(e => {
        setDatesError(e instanceof Error ? e.message : "Could not load shoot dates")
        setDatesLoading(false)
      })
  }, [activeTab, client])

  function handleTabChange(tab: string) {
    if (tab === activeTab) return
    if (Object.keys(batchResults).length > 0 && !batchRunning) {
      const ok = window.confirm(
        `Switching tabs clears ${Object.keys(batchResults).length} batch result${Object.keys(batchResults).length === 1 ? "" : "s"}. Continue?`,
      )
      if (!ok) return
    }
    setActiveTab(tab)
  }

  const batchResultsList = dates.map(d => ({ date: d.date_display, ...batchResults[d.date_key] }))
    .filter(r => r.url !== undefined || r.error !== undefined)

  return (
    <div>
      <PageHeader
        title="Call Sheets"
        eyebrow={activeTab ? `Production · ${activeTab}` : "Production · Call Sheets"}
        actions={
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--color-text-muted)" }}>
            Door
            <input
              type={showDoorCode ? "text" : "password"}
              value={doorCode}
              onChange={e => setDoorCode(e.target.value)}
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
                width: 64,
                padding: "4px 8px",
                fontSize: 12,
                fontFamily: showDoorCode ? "var(--font-mono)" : undefined,
                letterSpacing: showDoorCode ? 0 : "0.15em",
                outline: "none",
              }}
            />
            <button
              type="button"
              onClick={() => setShowDoorCode(v => !v)}
              aria-pressed={showDoorCode}
              style={{
                fontSize: 9,
                fontWeight: 600,
                padding: "3px 8px",
                background: "transparent",
                color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
                cursor: "pointer",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
              }}
            >
              {showDoorCode ? "Hide" : "Show"}
            </button>
          </label>
        }
      />

      {tabsLoading && <CallSheetsSkeleton />}
      {tabsError && <ErrorAlert className="mb-4">{tabsError}</ErrorAlert>}

      {/* Tab selector */}
      {tabs.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <TabSelector tabs={tabs} active={activeTab} onChange={handleTabChange} disabled={batchRunning} />
        </div>
      )}

      {/* Batch bar */}
      {dates.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={generateAll}
              disabled={batchRunning}
              style={{
                padding: "7px 14px",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                background: batchRunning
                  ? "var(--color-elevated)"
                  : batchDone
                  ? "color-mix(in srgb, var(--color-ok) 15%, transparent)"
                  : "var(--color-lime)",
                color: batchRunning
                  ? "var(--color-text-muted)"
                  : batchDone
                  ? "var(--color-ok)"
                  : "var(--color-lime-ink)",
                border: `1px solid ${
                  batchRunning
                    ? "var(--color-border)"
                    : batchDone
                    ? "color-mix(in srgb, var(--color-ok) 30%, transparent)"
                    : "var(--color-lime)"
                }`,
                cursor: batchRunning ? "wait" : "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {batchRunning
                ? `Generating ${batchProgress}/${batchTotal}…`
                : batchDone
                ? "✓ All Generated"
                : `Generate All (${dates.length})`}
            </button>
            {batchRunning && (
              <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
                <div style={{ maxWidth: 200, flex: 1, height: 4, background: "var(--color-border)", overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${(batchProgress / batchTotal) * 100}%`,
                      background: "var(--color-lime)",
                      transition: "width 300ms",
                    }}
                  />
                </div>
                {batchCurrentDate && (
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                    {batchCurrentDate}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Batch results log */}
          {batchResultsList.length > 0 && !batchRunning && (
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 3 }}>
              {batchResultsList.map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                  <span style={{ color: r.url ? "var(--color-ok)" : "var(--color-err)" }}>
                    {r.url ? "✓" : "✗"}
                  </span>
                  <span style={{ color: "var(--color-text-muted)" }}>{r.date}</span>
                  {r.url && (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--color-lime)", textDecoration: "none", fontSize: 10, letterSpacing: "0.06em" }}
                    >
                      Open ↗
                    </a>
                  )}
                  {r.error && <span style={{ color: "var(--color-err)" }}>{r.error}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Loading / error */}
      {datesLoading && <CallSheetsSkeleton />}
      {datesError && <ErrorAlert className="mb-4">{datesError}</ErrorAlert>}

      {/* Empty state */}
      {!datesLoading && dates.length === 0 && activeTab && !datesError && (
        <div
          style={{
            border: "1px solid var(--color-border)",
            padding: "28px 18px",
            textAlign: "center",
            marginTop: 8,
          }}
        >
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: "-0.02em",
              color: "var(--color-text)",
              marginBottom: 6,
            }}
          >
            No dates in {activeTab}.
          </div>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", maxWidth: 360, margin: "0 auto" }}>
            This budget tab has no shoot dates scheduled yet — come back once the production calendar is filled in.
          </p>
        </div>
      )}

      {/* Card grid */}
      {dates.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
            gap: 12,
          }}
        >
          {dates.map(d => (
            <DateCard
              key={d.date_key}
              date={d}
              doorCode={doorCode}
              idToken={idToken}
              tabName={activeTab}
              batchResult={batchResults[d.date_key]}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function CallSheetsSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }} aria-label="Loading…" aria-live="polite">
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 14px",
            border: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            opacity: 1 - i * 0.15,
          }}
        >
          <SkeletonBar width={72} />
          <SkeletonBar width={120} />
          <SkeletonBar width={56} />
          <div style={{ flex: 1 }} />
          <SkeletonBar width={48} />
        </div>
      ))}
    </div>
  )
}
