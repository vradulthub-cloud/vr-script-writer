"use client"

import { useState, useEffect, useMemo } from "react"
import { api } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { StudioBadge } from "@/components/ui/studio-badge"
import { PageHeader } from "@/components/ui/page-header"
import { SkeletonBar } from "@/components/ui/skeleton"
import type { ShootDate, ShootScene } from "@/lib/api"

// ---------------------------------------------------------------------------
// Date row component
// ---------------------------------------------------------------------------

interface DateRowProps {
  date: ShootDate
  doorCode: string
  idToken: string | undefined
  tabName: string
}

function DateRow({ date, doorCode, idToken, tabName }: DateRowProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ url: string; title: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function generate() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api(idToken ?? null).callSheets.generate({
        date_key: date.date_key,
        door_code: doorCode,
        tab_name: tabName || undefined,
      })
      setResult({ url: data.doc_url, title: data.title })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed")
    } finally {
      setLoading(false)
    }
  }

  const talent = [...new Set(date.scenes.flatMap(s => [s.female, s.male]).filter(Boolean))]

  return (
    <div
      className="rounded overflow-hidden"
      style={{ border: "1px solid var(--color-border)", marginBottom: 6 }}
    >
      {/* Header row */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-[--color-elevated] transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <span style={{ fontSize: 12, color: "var(--color-text)", fontWeight: 600, minWidth: 80 }}>
          {date.date_display}
        </span>
        <div className="flex gap-1 flex-wrap">
          {[...new Set(date.scenes.map(s => s.studio))].map(s => (
            <StudioBadge key={s} studio={s} />
          ))}
        </div>
        <span style={{ fontSize: 12, color: "var(--color-text-muted)", marginLeft: 4 }}>
          {talent.join(" / ")}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {result && (
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="px-2.5 py-1 rounded text-xs"
              style={{
                background: "color-mix(in srgb, var(--color-ok) 15%, transparent)",
                color: "var(--color-ok)",
                border: "1px solid color-mix(in srgb, var(--color-ok) 30%, transparent)",
              }}
            >
              Open Doc ↗
            </a>
          )}
          <button
            onClick={e => { e.stopPropagation(); generate() }}
            disabled={loading}
            className="px-3 py-1 rounded text-xs font-semibold transition-colors"
            style={{
              background: loading ? "var(--color-elevated)" : "var(--color-lime)",
              color: loading ? "var(--color-text-muted)" : "var(--color-lime-ink)",
              cursor: loading ? "wait" : "pointer",
            }}
          >
            {loading ? "Generating…" : result ? "Regenerate" : "Generate"}
          </button>
          <span
            style={{
              fontSize: 12,
              color: "var(--color-text-faint)",
              transform: open ? "rotate(180deg)" : undefined,
              display: "inline-block",
              transition: "transform 0.15s",
            }}
          >
            ▾
          </span>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 pb-2">
          <ErrorAlert className="text-xs">{error}</ErrorAlert>
        </div>
      )}

      {/* Expanded scene list */}
      {open && (
        <div style={{ borderTop: "1px solid var(--color-border)" }}>
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)" }}>
                {["Studio", "Type", "Female", "Male", "Agency"].map(h => (
                  <th key={h} className="text-left px-4 py-1.5 font-medium" style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {date.scenes.map((scene, i) => (
                <tr
                  key={i}
                  style={{ borderTop: "1px solid var(--color-border-subtle)" }}
                >
                  <td className="px-4 py-1.5"><StudioBadge studio={scene.studio} /></td>
                  <td className="px-4 py-1.5" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{scene.type || "—"}</td>
                  <td className="px-4 py-1.5" style={{ fontSize: 12, color: "var(--color-text)" }}>{scene.female || "—"}</td>
                  <td className="px-4 py-1.5" style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{scene.male || "—"}</td>
                  <td className="px-4 py-1.5" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{scene.agency || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
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

  // Batch generate state
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchProgress, setBatchProgress] = useState(0)
  const [batchTotal, setBatchTotal] = useState(0)
  const [batchResults, setBatchResults] = useState<{ date: string; url?: string; error?: string }[]>([])

  async function generateAll() {
    if (dates.length === 0 || batchRunning) return
    setBatchRunning(true)
    setBatchTotal(dates.length)
    setBatchProgress(0)
    setBatchResults([])
    const results: { date: string; url?: string; error?: string }[] = []

    for (let i = 0; i < dates.length; i++) {
      setBatchProgress(i + 1)
      const d = dates[i]
      try {
        const data = await client.callSheets.generate({
          date_key: d.date_key,
          door_code: doorCode,
          tab_name: activeTab || undefined,
        })
        results.push({ date: d.date_display, url: data.doc_url })
      } catch (e) {
        results.push({ date: d.date_display, error: e instanceof Error ? e.message : "Failed" })
      }
    }
    setBatchResults(results)
    setBatchRunning(false)
  }

  // Load tabs client-side only if the server didn't hydrate them (e.g. stale
  // session). The normal path has initialTabs from the server.
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

  // Load dates when tab changes
  useEffect(() => {
    if (!activeTab) return
    setDatesLoading(true)
    setDatesError(null)
    setDates([])
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

  return (
    <div>
      <PageHeader
        title="Call Sheets"
        eyebrow={activeTab ? `${activeTab} · door set` : "generate per-shoot call sheets"}
        actions={
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--color-text-muted)" }}>
            Door code
            <input
              // TKT-0101: door is a physical access code; hide by default so
              // it doesn't live in the page header readable to shoulder-surfers.
              type={showDoorCode ? "text" : "password"}
              value={doorCode}
              onChange={e => setDoorCode(e.target.value)}
              className="px-2.5 py-1.5 rounded text-xs outline-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
                width: 72,
                fontFamily: showDoorCode ? "var(--font-mono)" : undefined,
                letterSpacing: showDoorCode ? 0 : "0.15em",
              }}
            />
            <button
              type="button"
              onClick={() => setShowDoorCode(v => !v)}
              aria-pressed={showDoorCode}
              aria-label={showDoorCode ? "Hide door code" : "Show door code"}
              className="px-2 py-1 rounded transition-colors"
              style={{
                fontSize: 10,
                fontWeight: 500,
                background: "transparent",
                color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
                cursor: "pointer",
              }}
            >
              {showDoorCode ? "Hide" : "Show"}
            </button>
          </label>
        }
      />

      {/* Loading / error states */}
      {tabsLoading && <CallSheetsSkeleton />}
      {tabsError && <ErrorAlert className="mb-4">{tabsError}</ErrorAlert>}

      {/* Tab selector */}
      {tabs.length > 0 && (
        <div className="flex gap-1 mb-4 flex-wrap">
          {tabs.map(tab => (
            <button
              key={tab}
              disabled={batchRunning}
              onClick={() => {
                if (tab === activeTab) return
                // Switching tabs triggers a new dates fetch that clears
                // batchResults. If a batch is in progress, warn before
                // clobbering partial output.
                if (batchResults.length > 0 && !batchRunning) {
                  const ok = window.confirm(
                    `Switching tabs clears ${batchResults.length} batch result${batchResults.length === 1 ? "" : "s"}. Continue?`,
                  )
                  if (!ok) return
                }
                setActiveTab(tab)
              }}
              className="px-3 py-1.5 rounded text-xs transition-colors"
              style={{
                background: activeTab === tab ? "var(--color-elevated)" : "transparent",
                color: activeTab === tab ? "var(--color-text)" : "var(--color-text-muted)",
                border: `1px solid ${activeTab === tab ? "var(--color-border)" : "transparent"}`,
              }}
            >
              {tab}
            </button>
          ))}
        </div>
      )}

      {/* Generate All button + batch progress */}
      {dates.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-3">
            <button
              onClick={generateAll}
              disabled={batchRunning}
              className="px-4 py-1.5 rounded text-xs font-semibold transition-colors"
              style={{
                background: batchRunning ? "var(--color-elevated)" : "var(--color-lime)",
                color: batchRunning ? "var(--color-text-muted)" : "var(--color-lime-ink)",
                cursor: batchRunning ? "wait" : "pointer",
              }}
            >
              {batchRunning
                ? `Generating ${batchProgress}/${batchTotal}…`
                : `Generate All for ${activeTab}`}
            </button>
            {batchRunning && (
              <div className="flex-1 rounded-full overflow-hidden" style={{ height: 4, background: "var(--color-border)", maxWidth: 200 }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(batchProgress / batchTotal) * 100}%`,
                    background: "var(--color-lime)",
                  }}
                />
              </div>
            )}
          </div>

          {/* Batch results */}
          {batchResults.length > 0 && !batchRunning && (
            <div className="mt-3 flex flex-col gap-1">
              {batchResults.map((r, i) => (
                <div key={i} className="flex items-center gap-2" style={{ fontSize: 11 }}>
                  {r.url ? (
                    <>
                      <span style={{ color: "var(--color-ok)" }}>&#10003;</span>
                      <span style={{ color: "var(--color-text-muted)" }}>{r.date}</span>
                      <a href={r.url} target="_blank" rel="noopener noreferrer"
                        style={{ color: "var(--color-lime)" }}
                      >Open Doc ↗</a>
                    </>
                  ) : (
                    <>
                      <span style={{ color: "var(--color-err)" }}>&#10007;</span>
                      <span style={{ color: "var(--color-text-muted)" }}>{r.date}</span>
                      <span style={{ color: "var(--color-err)" }}>{r.error}</span>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Dates */}
      {datesLoading && <CallSheetsSkeleton />}
      {datesError && <ErrorAlert className="mb-4">{datesError}</ErrorAlert>}

      {!datesLoading && dates.length === 0 && activeTab && !datesError && (
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            padding: "28px 18px",
            textAlign: "center",
            marginTop: 8,
          }}
        >
          <div style={{ fontFamily: "var(--font-display-hero)", fontSize: 22, fontWeight: 400, letterSpacing: "-0.02em", color: "var(--color-text)", marginBottom: 6 }}>
            No dates in {activeTab}.
          </div>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", maxWidth: 360, margin: "0 auto" }}>
            This budget tab has no shoot dates scheduled yet — come back once the production calendar is filled in.
          </p>
        </div>
      )}

      {dates.map(d => (
        <DateRow
          key={d.date_key}
          date={d}
          doorCode={doorCode}
          idToken={idToken}
          tabName={activeTab}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton — shown while budget tabs / dates are loading. Matches the
// eventual DateRow shape (compact header row) so the transition to real
// content doesn't shift layout.
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
            borderRadius: 6,
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

