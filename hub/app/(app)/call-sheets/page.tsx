"use client"

import { useState, useEffect } from "react"
import { API_BASE_URL } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import type { ShootDate, ShootScene } from "@/lib/api"

// ---------------------------------------------------------------------------
// Studio badge colors for scene type rows
// ---------------------------------------------------------------------------

function StudioChip({ studio }: { studio: string }) {
  const color = STUDIO_COLOR[studio]
  return (
    <span
      className="px-1.5 py-0.5 rounded text-xs"
      style={{
        background: color ? `color-mix(in srgb, ${color} 15%, transparent)` : "var(--color-elevated)",
        color: color ?? "var(--color-text-muted)",
        fontSize: 10,
      }}
    >
      {studio === "FuckPassVR" ? "FPVR" :
       studio === "NaughtyJOI" ? "NJOI" :
       studio === "VRHush" ? "VRH" :
       studio === "VRAllure" ? "VRA" :
       studio}
    </span>
  )
}

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
      const res = await fetch(`${API_BASE_URL}/api/call-sheets/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          date_key: date.date_key,
          door_code: doorCode,
          tab_name: tabName || undefined,
        }),
      })
      if (!res.ok) {
        const txt = await res.text().catch(() => "")
        try {
          const json = JSON.parse(txt)
          throw new Error(json.detail ?? txt)
        } catch {
          throw new Error(txt || `HTTP ${res.status}`)
        }
      }
      const data = await res.json()
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
            <StudioChip key={s} studio={s} />
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
              color: loading ? "var(--color-text-muted)" : "#0d0d0d",
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
                  <td className="px-4 py-1.5"><StudioChip studio={scene.studio} /></td>
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

export default function CallSheetsPage() {
  const idToken = useIdToken(undefined)

  const [tabs, setTabs] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<string>("")
  const [dates, setDates] = useState<ShootDate[]>([])
  const [doorCode, setDoorCode] = useState("1322")
  const [tabsLoading, setTabsLoading] = useState(true)
  const [datesLoading, setDatesLoading] = useState(false)
  const [tabsError, setTabsError] = useState<string | null>(null)
  const [datesError, setDatesError] = useState<string | null>(null)

  // Load tabs once we have an idToken
  useEffect(() => {
    if (!idToken) return
    setTabsLoading(true)
    setTabsError(null)
    fetch(`${API_BASE_URL}/api/call-sheets/tabs`, {
      headers: { Authorization: `Bearer ${idToken}` },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<string[]>
      })
      .then(data => {
        setTabs(data)
        if (data.length > 0) setActiveTab(data[0])
        setTabsLoading(false)
      })
      .catch(e => {
        setTabsError(e instanceof Error ? e.message : "Could not load tabs")
        setTabsLoading(false)
      })
  }, [idToken])

  // Load dates when tab changes
  useEffect(() => {
    if (!idToken || !activeTab) return
    setDatesLoading(true)
    setDatesError(null)
    setDates([])
    fetch(`${API_BASE_URL}/api/call-sheets/dates?tab=${encodeURIComponent(activeTab)}`, {
      headers: { Authorization: `Bearer ${idToken}` },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<ShootDate[]>
      })
      .then(data => {
        setDates(data)
        setDatesLoading(false)
      })
      .catch(e => {
        setDatesError(e instanceof Error ? e.message : "Could not load shoot dates")
        setDatesLoading(false)
      })
  }, [idToken, activeTab])

  return (
    <div>
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-semibold tracking-tight" style={{ fontSize: 16, color: "var(--color-text)" }}>
            Call Sheets
          </h1>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
            Shoot day logistics — generate Google Doc call sheets from the budget sheet
          </p>
        </div>

        {/* Door code */}
        <div className="flex items-center gap-2">
          <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Door code</label>
          <input
            type="text"
            value={doorCode}
            onChange={e => setDoorCode(e.target.value)}
            className="px-2.5 py-1.5 rounded text-xs outline-none"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text)",
              width: 72,
            }}
          />
        </div>
      </div>

      {/* Loading / error states */}
      {tabsLoading && (
        <p style={{ fontSize: 12, color: "var(--color-text-faint)" }}>Loading budget tabs…</p>
      )}
      {tabsError && <ErrorAlert className="mb-4">{tabsError}</ErrorAlert>}

      {/* Tab selector */}
      {tabs.length > 0 && (
        <div className="flex gap-1 mb-4 flex-wrap">
          {tabs.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
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

      {/* Dates */}
      {datesLoading && (
        <p style={{ fontSize: 12, color: "var(--color-text-faint)" }}>Loading shoot dates…</p>
      )}
      {datesError && <ErrorAlert className="mb-4">{datesError}</ErrorAlert>}

      {!datesLoading && dates.length === 0 && activeTab && !datesError && (
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>No shoot dates found in {activeTab}.</p>
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
