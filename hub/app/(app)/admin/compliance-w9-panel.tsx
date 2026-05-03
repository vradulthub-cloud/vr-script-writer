"use client"

import { useEffect, useMemo, useState } from "react"
import { CheckCircle2, Download, FileSpreadsheet, FolderOpen, Loader2, RefreshCw } from "lucide-react"
import { api, type BulkDriveImportResult, type W9Summary } from "@/lib/api"

/**
 * Admin-only W-9 / talent tax records export (TKT-0153).
 *
 * Lets the admin pick a date range + optional studio, see a summary count,
 * and download an .xlsx for the accountant. The spreadsheet is rendered
 * server-side so PII never lives in the Hub's client memory — this panel
 * just shows the count and triggers the download URL in a new tab.
 */

interface Props {
  idToken: string | undefined
}

const STUDIOS = ["", "FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const

function defaultRange(): { from: string; to: string } {
  // Default to year-to-date so the accountant gets the typical tax-year window.
  const now = new Date()
  const year = now.getUTCFullYear()
  const pad = (n: number) => String(n).padStart(2, "0")
  return {
    from: `${year}-01-01`,
    to: `${year}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())}`,
  }
}

export function ComplianceW9Panel({ idToken }: Props) {
  const client = useMemo(() => api(idToken ?? null), [idToken])
  const init = defaultRange()

  const [from, setFrom] = useState(init.from)
  const [to, setTo] = useState(init.to)
  const [studio, setStudio] = useState<string>("")
  const [summary, setSummary] = useState<W9Summary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Bulk-import state
  const [bulkUrl, setBulkUrl] = useState("")
  const [bulkLabel, setBulkLabel] = useState("")
  const [bulkSubmitting, setBulkSubmitting] = useState(false)
  const [bulkResult, setBulkResult] = useState<BulkDriveImportResult | null>(null)
  const [bulkError, setBulkError] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const r = await client.compliance.w9Summary({ from, to, studio: studio || undefined })
      setSummary(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load summary")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [])

  const downloadHref = client.compliance.w9ExportUrl({ from, to, studio: studio || undefined })

  async function runBulkImport() {
    if (!bulkUrl.trim()) return
    setBulkSubmitting(true)
    setBulkError(null)
    setBulkResult(null)
    try {
      const r = await client.compliance.bulkImportFromDrive(bulkUrl.trim(), bulkLabel.trim() || undefined)
      setBulkResult(r)
      void refresh()
    } catch (e) {
      setBulkError(e instanceof Error ? e.message : "Bulk import failed")
    } finally {
      setBulkSubmitting(false)
    }
  }

  return (
    <div>
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start",
    }}>
      {/* Left — filters + download */}
      <section style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 12,
        padding: "18px 20px",
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 10, marginBottom: 6,
        }}>
          <FileSpreadsheet size={16} color="var(--color-lime)" />
          <h3 style={{
            margin: 0, fontSize: 14, fontWeight: 700, letterSpacing: "0.02em",
            color: "var(--color-text)",
          }}>
            W-9 / Tax Records Export
          </h3>
        </div>
        <p style={{
          margin: "0 0 16px", fontSize: 12, color: "var(--color-text-faint)", lineHeight: 1.55,
        }}>
          Spreadsheet of every talent W-9 + 2257 record on file, formatted for handoff
          to the accountant. SSN/EIN and phone numbers are pre-formatted; the linked
          PDF path is included so the source artifact can be pulled on demand.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
          <Field label="From">
            <input
              type="date"
              value={from}
              onChange={e => setFrom(e.target.value)}
              style={dateInputStyle}
            />
          </Field>
          <Field label="To">
            <input
              type="date"
              value={to}
              onChange={e => setTo(e.target.value)}
              style={dateInputStyle}
            />
          </Field>
        </div>

        <Field label="Studio (optional)">
          <select
            value={studio}
            onChange={e => setStudio(e.target.value)}
            style={{
              ...dateInputStyle,
              appearance: "none", WebkitAppearance: "none",
              backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>")`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "right 12px center",
              paddingRight: 32,
            }}
          >
            {STUDIOS.map(s => (
              <option key={s} value={s}>{s || "All studios"}</option>
            ))}
          </select>
        </Field>

        {error && (
          <div style={{
            marginTop: 12,
            background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 8, padding: "9px 12px",
            fontSize: 12, color: "#f87171",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            style={{
              background: "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: "9px 12px",
              fontSize: 12, fontWeight: 600,
              color: "var(--color-text-muted)",
              cursor: loading ? "not-allowed" : "pointer",
              display: "inline-flex", alignItems: "center", gap: 6,
            }}
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Refresh count
          </button>
          <a
            href={downloadHref}
            target="_blank"
            rel="noopener noreferrer"
            aria-disabled={summary?.total === 0}
            onClick={e => { if (summary?.total === 0) e.preventDefault() }}
            style={{
              flex: 1,
              background: summary?.total ? "var(--color-lime)" : "var(--color-elevated)",
              border: "none",
              borderRadius: 8,
              padding: "10px 14px",
              fontSize: 13, fontWeight: 700,
              color: summary?.total ? "#000" : "var(--color-text-faint)",
              cursor: summary?.total ? "pointer" : "not-allowed",
              textDecoration: "none",
              display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
            }}
          >
            <Download size={14} /> Download .xlsx
          </a>
        </div>
      </section>

      {/* Right — summary */}
      <section style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 12,
        padding: "18px 20px",
      }}>
        <h3 style={{
          margin: "0 0 12px", fontSize: 14, fontWeight: 700, letterSpacing: "0.02em",
          color: "var(--color-text)",
        }}>
          In this range
        </h3>

        {loading && (
          <div style={{ fontSize: 12, color: "var(--color-text-faint)", display: "flex", alignItems: "center", gap: 6 }}>
            <Loader2 size={12} className="animate-spin" /> Counting…
          </div>
        )}

        {!loading && summary && (
          <>
            <div style={{
              fontSize: 36, fontWeight: 700, color: "var(--color-text)",
              fontFamily: "var(--font-display-hero)", lineHeight: 1.1,
            }}>
              {summary.total.toLocaleString()}
            </div>
            <div style={{ fontSize: 12, color: "var(--color-text-faint)", marginTop: 2 }}>
              record{summary.total === 1 ? "" : "s"} · {summary.by_role.female || 0} female · {summary.by_role.male || 0} male
            </div>

            <div style={{
              marginTop: 14, paddingTop: 12,
              borderTop: "1px solid var(--color-border-subtle)",
              fontSize: 11, color: "var(--color-text-faint)",
              letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8,
            }}>
              By Studio
            </div>
            {Object.keys(summary.by_studio).length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>
                Nothing in this range yet.
              </div>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 5 }}>
                {Object.entries(summary.by_studio)
                  .sort(([, a], [, b]) => b - a)
                  .map(([s, n]) => (
                    <li key={s} style={{
                      display: "flex", justifyContent: "space-between",
                      fontSize: 12.5, color: "var(--color-text)",
                    }}>
                      <span>{s}</span>
                      <span style={{ fontVariantNumeric: "tabular-nums", color: "var(--color-text-muted)" }}>
                        {n}
                      </span>
                    </li>
                  ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>

    {/* Bulk import — back-fill an entire 2026 paperwork root in one shot. */}
    <section style={{
      marginTop: 16,
      background: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      borderRadius: 12,
      padding: "18px 20px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <FolderOpen size={16} color="var(--color-text-muted)" />
        <h3 style={{
          margin: 0, fontSize: 14, fontWeight: 700, letterSpacing: "0.02em",
          color: "var(--color-text)",
        }}>
          Bulk import from Drive
        </h3>
      </div>
      <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--color-text-faint)", lineHeight: 1.55 }}>
        Walks a Drive root recursively. Each shoot folder named
        <span style={{ fontFamily: "var(--font-mono)", margin: "0 4px", color: "var(--color-text-muted)" }}>
          MMDDYY-FemaleSlug[-MaleSlug]
        </span>
        is matched to its local shoot, every contained PDF gets copied to MEGA, and a thin compliance row is upserted. Safe to re-run.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10, marginBottom: 12 }}>
        <Field label="Drive root URL">
          <input
            type="url"
            placeholder="https://drive.google.com/drive/folders/…"
            value={bulkUrl}
            onChange={e => setBulkUrl(e.target.value)}
            style={{ ...dateInputStyle, fontFamily: "var(--font-mono)" }}
          />
        </Field>
        <Field label="Audit label (optional)">
          <input
            type="text"
            placeholder="e.g. Drive 2026"
            value={bulkLabel}
            onChange={e => setBulkLabel(e.target.value)}
            style={dateInputStyle}
          />
        </Field>
      </div>

      {bulkError && (
        <div style={{
          background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
          borderRadius: 8, padding: "9px 12px", marginBottom: 10,
          fontSize: 12, color: "#f87171",
        }}>
          {bulkError}
        </div>
      )}

      <button
        type="button"
        onClick={runBulkImport}
        disabled={!bulkUrl.trim() || bulkSubmitting}
        style={{
          background: !bulkUrl.trim() || bulkSubmitting ? "var(--color-elevated)" : "var(--color-lime)",
          border: "none",
          borderRadius: 8,
          padding: "10px 16px",
          fontSize: 13, fontWeight: 700,
          color: !bulkUrl.trim() || bulkSubmitting ? "var(--color-text-faint)" : "#000",
          cursor: !bulkUrl.trim() || bulkSubmitting ? "not-allowed" : "pointer",
          display: "inline-flex", alignItems: "center", gap: 6,
        }}
      >
        {bulkSubmitting
          ? <><Loader2 size={13} className="animate-spin" /> Walking Drive…</>
          : <><FolderOpen size={13} /> Run bulk import</>
        }
      </button>

      {bulkResult && (
        <div style={{
          marginTop: 14,
          background: "var(--color-bg)", border: "1px solid var(--color-border-subtle)",
          borderRadius: 10, padding: "12px 14px",
          fontSize: 12, color: "var(--color-text-muted)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--color-text)", fontWeight: 600, marginBottom: 6 }}>
            <CheckCircle2 size={14} color="var(--color-lime)" />
            {bulkResult.folders_matched} of {bulkResult.folders_seen} folders matched · {bulkResult.shoots.reduce((s, x) => s + x.talents_imported, 0)} talents imported
          </div>
          {bulkResult.shoots.length > 0 && (
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 3 }}>
              {bulkResult.shoots.slice(0, 25).map((s, i) => (
                <li key={i} style={{
                  display: "flex", justifyContent: "space-between", gap: 8,
                  fontSize: 11.5, color: "var(--color-text-muted)",
                }}>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-faint)" }}>{s.shoot_date}</span>
                  <span style={{ flex: 1 }}>{s.folder_name}</span>
                  <span style={{ color: s.talents_imported > 0 ? "var(--color-lime)" : "var(--color-text-faint)" }}>
                    {s.skipped_reason ? `skipped — ${s.skipped_reason}` : `+${s.talents_imported}`}
                  </span>
                </li>
              ))}
              {bulkResult.shoots.length > 25 && (
                <li style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 4 }}>
                  … and {bulkResult.shoots.length - 25} more
                </li>
              )}
            </ul>
          )}
          {bulkResult.errors.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 11, color: "#f87171" }}>
              {bulkResult.errors.length} error{bulkResult.errors.length === 1 ? "" : "s"}: {bulkResult.errors.slice(0, 3).join("; ")}
              {bulkResult.errors.length > 3 && "…"}
            </div>
          )}
        </div>
      )}
    </section>
    </div>
  )
}

const dateInputStyle: React.CSSProperties = {
  width: "100%",
  background: "var(--color-elevated)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  padding: "9px 12px",
  fontSize: 12.5,
  color: "var(--color-text)",
  outline: "none",
  boxSizing: "border-box",
  fontFamily: "inherit",
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{
        fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
        textTransform: "uppercase", color: "var(--color-text-faint)",
        marginBottom: 5,
      }}>
        {label}
      </div>
      {children}
    </div>
  )
}
