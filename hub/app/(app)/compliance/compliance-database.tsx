"use client"

/**
 * Compliance "Database" — the searchable index of every paperwork record.
 *
 * Sits behind a tab toggle on the Compliance page (Wizard | Database). The
 * wizard remains the primary on-set workflow; this view is for admins who
 * need to find historical records, audit signed paperwork, or pull a single
 * PDF/photo from years ago.
 *
 * Two data sources, merged into one table:
 *   - DB rows from compliance_signatures (structured, editable, render-as-PDF)
 *   - MEGA-only legacy files inside {SCENE_ID}/Legal/ folders (download-only)
 *
 * Click a row → opens the existing SignatureEditModal for DB rows, or a
 * presigned MEGA download for legacy rows. CSV export operates on the
 * filtered set so an admin can hand a slice to the accountant without
 * waiting on the server-side xlsx export.
 */

import { useEffect, useMemo, useRef, useState } from "react"
import {
  AlertTriangle,
  Database,
  Download,
  DownloadCloud,
  ExternalLink,
  FileText,
  HardDrive,
  Loader2,
  Pencil,
  RefreshCw,
  Search,
  X,
} from "lucide-react"
import {
  api,
  type MegaImportResult,
  type MegaLegalFile,
  type SignatureSearchHit,
} from "@/lib/api"
import { SignatureEditModal } from "./signature-edit-modal"

// ─── Studio mappings (mirror compliance-view.tsx for visual parity) ──────────

const STUDIO_COLOR: Record<string, string> = {
  FuckPassVR: "#f97316",
  VRHush:     "#8b5cf6",
  VRAllure:   "#ec4899",
  NaughtyJOI: "#3b82f6",
  // 4-letter codes (used by MEGA scan rows)
  FPVR: "#f97316",
  VRH:  "#8b5cf6",
  VRA:  "#ec4899",
  NJOI: "#3b82f6",
}

const CODE_TO_NAME: Record<string, string> = {
  FPVR: "FuckPassVR",
  VRH:  "VRHush",
  VRA:  "VRAllure",
  NJOI: "NaughtyJOI",
}

const NAME_TO_CODE: Record<string, string> = {
  FuckPassVR: "FPVR",
  VRHush:     "VRH",
  VRAllure:   "VRA",
  NaughtyJOI: "NJOI",
}

function studioColor(s: string): string {
  return STUDIO_COLOR[s] ?? "var(--color-lime)"
}
function studioCode(s: string): string {
  return NAME_TO_CODE[s] ?? s
}
function studioName(code: string): string {
  return CODE_TO_NAME[code] ?? code
}

// ─── Types ───────────────────────────────────────────────────────────────────

type Source = "db" | "mega"

interface DbRow {
  source: "db"
  hit: SignatureSearchHit
}

interface MegaRow {
  source: "mega"
  file: MegaLegalFile
}

type Row = DbRow | MegaRow

const STUDIO_OPTIONS = ["", "FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"] as const
const ROLE_OPTIONS   = ["", "female", "male"] as const

// ─── Component ───────────────────────────────────────────────────────────────

export function ComplianceDatabase({ idToken }: { idToken: string | undefined }) {
  const client = useMemo(() => api(idToken ?? null), [idToken])

  // Filters
  const [query, setQuery]       = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo]     = useState("")
  const [studio, setStudio]     = useState<string>("")
  const [role, setRole]         = useState<string>("")
  const [includeMega, setIncludeMega] = useState(true)
  const [includeDb, setIncludeDb]     = useState(true)

  // Data
  const [hits, setHits]               = useState<SignatureSearchHit[]>([])
  const [hitsTotal, setHitsTotal]     = useState(0)
  const [megaFiles, setMegaFiles]     = useState<MegaLegalFile[]>([])
  const [megaScannedAt, setMegaScannedAt] = useState<string | null>(null)
  const [megaTruncated, setMegaTruncated] = useState(false)

  // Status
  const [loadingDb, setLoadingDb]     = useState(false)
  const [loadingMega, setLoadingMega] = useState(false)
  const [dbError, setDbError]         = useState<string | null>(null)
  const [megaError, setMegaError]     = useState<string | null>(null)

  // Selection (modal open)
  const [editingId, setEditingId] = useState<number | null>(null)

  // MEGA file rename modal — opens when an admin clicks the pencil icon
  // on a MEGA row. Destructive (COPY + DELETE on the bucket), so there's
  // an explicit confirmation step before the API call goes out.
  const [renameTarget, setRenameTarget] = useState<MegaLegalFile | null>(null)
  const [renameDraft,  setRenameDraft]  = useState("")
  const [renaming,     setRenaming]     = useState(false)
  const [renameError,  setRenameError]  = useState<string | null>(null)

  // Bulk MEGA → DB importer
  const [importOpen, setImportOpen]           = useState(false)
  const [importRunning, setImportRunning]     = useState(false)
  const [importResult, setImportResult]       = useState<MegaImportResult | null>(null)
  const [importError, setImportError]         = useState<string | null>(null)
  const ytdFrom = `${new Date().getUTCFullYear()}-01-01`
  const todayUtc = new Date().toISOString().slice(0, 10)
  const [importFrom, setImportFrom]           = useState(ytdFrom)
  const [importTo, setImportTo]               = useState(todayUtc)
  const [importStudio, setImportStudio]       = useState<string>("")
  const [importOverwrite, setImportOverwrite] = useState(false)


  // Debounced query — re-fetch DB results as the user types.
  const queryDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Load DB results ──────────────────────────────────────────────────────
  async function loadDb(opts?: { silent?: boolean }) {
    if (!opts?.silent) setLoadingDb(true)
    setDbError(null)
    try {
      const r = await client.compliance.search({
        q: query || undefined,
        from: dateFrom || undefined,
        to: dateTo || undefined,
        studio: studio || undefined,
        role: (role || undefined) as "female" | "male" | undefined,
        limit: 500,
      })
      setHits(r.hits)
      setHitsTotal(r.total)
    } catch (e) {
      setDbError(e instanceof Error ? e.message : "Search failed")
      setHits([])
      setHitsTotal(0)
    } finally {
      setLoadingDb(false)
    }
  }

  // ── Load MEGA legacy files ───────────────────────────────────────────────
  async function loadMega(force = false) {
    setLoadingMega(true)
    setMegaError(null)
    try {
      const r = await client.compliance.legalFolders({
        studio: studio ? studioCode(studio) : undefined,
        refresh: force,
      })
      setMegaFiles(r.files)
      setMegaScannedAt(r.scanned_at)
      setMegaTruncated(r.truncated)
    } catch (e) {
      setMegaError(e instanceof Error ? e.message : "MEGA scan failed")
      setMegaFiles([])
    } finally {
      setLoadingMega(false)
    }
  }

  // Initial load + reload on filter change
  useEffect(() => {
    void loadDb()
    void loadMega(false)
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [])

  useEffect(() => {
    if (queryDebounceRef.current) clearTimeout(queryDebounceRef.current)
    queryDebounceRef.current = setTimeout(() => { void loadDb({ silent: true }) }, 250)
    return () => {
      if (queryDebounceRef.current) clearTimeout(queryDebounceRef.current)
    }
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [query])

  // Filter changes that hit the server → fetch DB; MEGA only refetches if
  // the studio filter changed (it has its own studio param) — date / role /
  // query are filtered client-side over the cached MEGA list.
  useEffect(() => {
    void loadDb({ silent: true })
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [dateFrom, dateTo, studio, role])

  useEffect(() => {
    void loadMega(false)
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [studio])

  // ── Filter MEGA files in-memory by query/date/role ───────────────────────
  const filteredMega = useMemo<MegaLegalFile[]>(() => {
    const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
    return megaFiles.filter(f => {
      // Date filter compares against last_modified (best signal we have)
      const dt = (f.last_modified || "").slice(0, 10)
      if (dateFrom && dt && dt < dateFrom) return false
      if (dateTo   && dt && dt > dateTo)   return false
      // Role filter is meaningless for raw MEGA files — exclude them when
      // the operator picks a role to keep the table coherent.
      if (role) return false
      const hay = `${f.studio} ${f.scene_id} ${f.filename} ${f.key}`.toLowerCase()
      for (const t of tokens) if (!hay.includes(t)) return false
      return true
    })
  }, [megaFiles, query, dateFrom, dateTo, role])

  // ── Merge into a single ordered list ─────────────────────────────────────
  const rows = useMemo<Row[]>(() => {
    const all: Row[] = []
    if (includeDb)   for (const h of hits) all.push({ source: "db", hit: h })
    if (includeMega) for (const f of filteredMega) all.push({ source: "mega", file: f })
    // DB rows expose shoot_date; MEGA rows fall back to last_modified.
    function rowDate(r: Row): string {
      return r.source === "db" ? r.hit.shoot_date : (r.file.last_modified || "")
    }
    all.sort((a, b) => {
      const da = rowDate(a), db = rowDate(b)
      if (da < db) return 1
      if (da > db) return -1
      return 0
    })
    return all
  }, [hits, filteredMega, includeDb, includeMega])

  // ── CSV export of filtered results ───────────────────────────────────────
  function exportCsv() {
    const headers = [
      "source", "shoot_date", "studio", "scene_id", "talent_role",
      "talent_display", "legal_name", "stage_names", "city_state_zip",
      "email", "phone", "tin_type", "tin_last4", "filename", "key", "size",
    ]
    const escape = (v: unknown): string => {
      const s = v == null ? "" : String(v)
      if (s.includes(",") || s.includes("\"") || s.includes("\n")) {
        return `"${s.replace(/"/g, '""')}"`
      }
      return s
    }
    const lines: string[] = [headers.join(",")]
    for (const r of rows) {
      if (r.source === "db") {
        const h = r.hit
        lines.push([
          "db", h.shoot_date, h.studio, h.scene_id, h.talent_role,
          h.talent_display, h.legal_name, h.stage_names, h.city_state_zip,
          h.email, h.phone, h.tin_type, h.tin_last4,
          (h.pdf_mega_path || "").split("/").pop() || "", h.pdf_mega_path || "", "",
        ].map(escape).join(","))
      } else {
        const f = r.file
        lines.push([
          "mega", (f.last_modified || "").slice(0, 10), studioName(f.studio), f.scene_id, "",
          "", "", "", "", "", "", "", "",
          f.filename, f.key, String(f.size),
        ].map(escape).join(","))
      }
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    const stamp = new Date().toISOString().slice(0, 10)
    a.href = url
    a.download = `eclatech-compliance-database_${stamp}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Open MEGA-only file via presigned URL ────────────────────────────────
  async function openMegaFile(file: MegaLegalFile) {
    try {
      const r = await client.compliance.legalFolderPresign(file.studio, file.key)
      window.open(r.url, "_blank", "noopener,noreferrer")
    } catch (e) {
      // Surface inline rather than throw — admins can refresh and retry.
      setMegaError(e instanceof Error ? e.message : "Could not generate download URL")
    }
  }

  function startRename(f: MegaLegalFile) {
    setRenameTarget(f)
    setRenameDraft(f.filename)
    setRenameError(null)
  }

  async function commitRename() {
    if (!renameTarget) return
    const newName = renameDraft.trim()
    if (!newName || newName === renameTarget.filename) {
      setRenameTarget(null)
      return
    }
    // Extension match enforced server-side, but the UX is friendlier if we
    // catch it before the round-trip.
    const oldExt = (renameTarget.filename.match(/\.[^.]+$/) || [""])[0].toLowerCase()
    const newExt = (newName.match(/\.[^.]+$/) || [""])[0].toLowerCase()
    if (oldExt !== newExt) {
      setRenameError(`Extension must stay ${oldExt} (got ${newExt || "(none)"})`)
      return
    }
    setRenaming(true)
    setRenameError(null)
    try {
      await client.compliance.legalFileRename(
        renameTarget.studio.toLowerCase(),
        renameTarget.key,
        newName,
      )
      setRenameTarget(null)
      setRenameDraft("")
      // Refresh both lists so the new filename appears.
      void loadDb({ silent: true })
      void loadMega(true)
    } catch (e) {
      setRenameError(e instanceof Error ? e.message : "Rename failed")
    } finally {
      setRenaming(false)
    }
  }

  async function runImport() {
    setImportRunning(true)
    setImportError(null)
    setImportResult(null)
    try {
      const r = await client.compliance.importFromMegaLegal({
        date_from: importFrom,
        date_to: importTo,
        studio: importStudio || undefined,
        overwrite_existing: importOverwrite,
        imported_from_label: `db-view-${todayUtc}`,
      })
      setImportResult(r)
      // Refresh both lists so newly imported rows appear and MEGA-only
      // rows that just got imported flip to "Records" rows.
      void loadDb({ silent: true })
      void loadMega(true)
    } catch (e) {
      setImportError(e instanceof Error ? e.message : "Import failed")
    } finally {
      setImportRunning(false)
    }
  }

  function clearFilters() {
    setQuery("")
    setDateFrom("")
    setDateTo("")
    setStudio("")
    setRole("")
  }

  const activeFilterCount = [query, dateFrom, dateTo, studio, role].filter(Boolean).length
  const lime = "var(--color-lime)"

  return (
    <div style={{ padding: "16px 16px 80px" }}>
      {/* ── Header strip ── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 12, gap: 12, flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Database size={16} color={lime} />
          <h2 style={{
            margin: 0, fontSize: 14, fontWeight: 700, letterSpacing: "0.02em",
            color: "var(--color-text)", textTransform: "uppercase",
          }}>
            Paperwork Database
          </h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            onClick={() => setImportOpen(v => !v)}
            style={importOpen
              ? { ...btnGhost, color: "var(--color-lime)", borderColor: "var(--color-lime)" }
              : btnGhost}
            title="Bulk-import MEGA Legal/ folder PDFs into the records DB"
          >
            <DownloadCloud size={13} />
            Import from MEGA
          </button>
          <button
            type="button"
            onClick={() => { void loadDb(); void loadMega(true) }}
            disabled={loadingDb || loadingMega}
            style={btnGhost}
            title="Refresh — re-runs the DB query and forces a fresh MEGA bucket scan"
          >
            {(loadingDb || loadingMega) ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
            Refresh
          </button>
          <button
            type="button"
            onClick={exportCsv}
            disabled={rows.length === 0}
            style={btnGhost}
            title="Download visible results as CSV"
          >
            <Download size={13} />
            CSV
          </button>
        </div>
      </div>

      {/* ── Import-from-MEGA panel (collapsible) ── */}
      {importOpen && (
        <div style={{
          background: "var(--color-elevated)",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          padding: "14px 16px",
          marginBottom: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <DownloadCloud size={14} color="var(--color-lime)" />
            <h3 style={{
              margin: 0, fontSize: 12, fontWeight: 700,
              letterSpacing: "0.04em", textTransform: "uppercase",
              color: "var(--color-text)",
            }}>
              Import MEGA paperwork into records
            </h3>
            <button
              type="button"
              onClick={() => setImportOpen(false)}
              aria-label="Close import panel"
              style={{
                marginLeft: "auto", background: "transparent", border: "none",
                color: "var(--color-text-faint)", cursor: "pointer",
                display: "flex", alignItems: "center", padding: 0,
              }}
            >
              <X size={14} />
            </button>
          </div>
          <p style={{
            margin: "0 0 12px", fontSize: 11, color: "var(--color-text-faint)", lineHeight: 1.5,
          }}>
            Walks each shoot in the date range, downloads every <code style={{
              background: "var(--color-surface)", padding: "0 4px", borderRadius: 3,
            }}>{"{SCENE_ID}/Legal/*.pdf"}</code>{" "}
            file, parses the AcroForm fields, and creates a structured record per
            matched talent. Skips shoots that already have records unless
            <em> Overwrite existing</em> is on.
          </p>
          <div style={{
            display: "grid", gridTemplateColumns: "auto auto auto auto 1fr auto", gap: 10, alignItems: "end",
          }}>
            <FilterField label="From">
              <input type="date" value={importFrom} onChange={e => setImportFrom(e.target.value)} style={inputCompact} />
            </FilterField>
            <FilterField label="To">
              <input type="date" value={importTo} onChange={e => setImportTo(e.target.value)} style={inputCompact} />
            </FilterField>
            <FilterField label="Studio">
              <select value={importStudio} onChange={e => setImportStudio(e.target.value)} style={inputCompact}>
                {STUDIO_OPTIONS.map(s => <option key={s || "all"} value={s}>{s || "All"}</option>)}
              </select>
            </FilterField>
            <label style={{
              display: "flex", alignItems: "center", gap: 6, fontSize: 11,
              color: "var(--color-text-faint)",
            }}>
              <input
                type="checkbox"
                checked={importOverwrite}
                onChange={e => setImportOverwrite(e.target.checked)}
              />
              Overwrite existing
            </label>
            <div />
            <button
              type="button"
              onClick={runImport}
              disabled={importRunning || !importFrom || !importTo}
              style={{
                ...btnGhost,
                background: "color-mix(in srgb, var(--color-lime) 16%, transparent)",
                color: "var(--color-lime)",
                borderColor: "var(--color-lime)",
              }}
            >
              {importRunning ? <Loader2 size={13} className="spin" /> : <DownloadCloud size={13} />}
              Run import
            </button>
          </div>
          {importError && (
            <div style={{
              marginTop: 10, padding: "6px 10px",
              background: "color-mix(in srgb, var(--color-danger) 12%, transparent)",
              border: "1px solid var(--color-danger)", borderRadius: 6,
              fontSize: 11, color: "var(--color-text)",
            }}>
              {importError}
            </div>
          )}
          {importResult && (
            <div style={{
              marginTop: 10, padding: "8px 12px",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)", borderRadius: 6,
              fontSize: 11, color: "var(--color-text)",
              display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8,
            }}>
              <Stat label="Shoots seen" value={importResult.shoots_seen} />
              <Stat label="Shoots processed" value={importResult.shoots_processed} />
              <Stat label="Talents imported" value={importResult.total_imported} highlight />
              {importResult.errors.length > 0 && (
                <div style={{
                  gridColumn: "1 / -1", color: "var(--color-danger)", fontSize: 10,
                }}>
                  {importResult.errors.length} errors — first: {importResult.errors[0]}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Search + filter row ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr",
        gap: 10,
        marginBottom: 14,
      }}>
        {/* Search input */}
        <div style={{ position: "relative" }}>
          <Search
            size={14}
            color="var(--color-text-faint)"
            style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)" }}
          />
          <input
            type="search"
            inputMode="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="Search talent, email, scene, address…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            style={{
              width: "100%",
              background: "var(--color-elevated)",
              border: "1px solid var(--color-border)",
              borderRadius: 10,
              padding: "11px 36px 11px 36px",
              fontSize: 13,
              color: "var(--color-text)",
              outline: "none",
              boxSizing: "border-box",
              fontFamily: "inherit",
            }}
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              aria-label="Clear search"
              style={{
                position: "absolute", right: 8, top: 0, bottom: 0,
                background: "transparent", border: "none",
                color: "var(--color-text-faint)", cursor: "pointer",
                display: "flex", alignItems: "center", padding: "0 6px",
              }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Filter row */}
        <div style={{
          display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8,
        }}>
          <FilterField label="From">
            <input
              type="date"
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
              style={inputCompact}
            />
          </FilterField>
          <FilterField label="To">
            <input
              type="date"
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
              style={inputCompact}
            />
          </FilterField>
          <FilterField label="Studio">
            <select
              value={studio}
              onChange={e => setStudio(e.target.value)}
              style={inputCompact}
            >
              {STUDIO_OPTIONS.map(s => (
                <option key={s || "all"} value={s}>{s || "All"}</option>
              ))}
            </select>
          </FilterField>
          <FilterField label="Role">
            <select
              value={role}
              onChange={e => setRole(e.target.value)}
              style={inputCompact}
            >
              {ROLE_OPTIONS.map(r => (
                <option key={r || "all"} value={r}>{r ? r[0].toUpperCase() + r.slice(1) : "All"}</option>
              ))}
            </select>
          </FilterField>

          <div style={{ flex: 1, minWidth: 8 }} />

          {/* Source toggles */}
          <SourceChip
            active={includeDb}
            onToggle={() => setIncludeDb(v => !v)}
            label={`Records (${hitsTotal})`}
            color={lime}
          />
          <SourceChip
            active={includeMega}
            onToggle={() => setIncludeMega(v => !v)}
            label={`MEGA (${filteredMega.length}${megaTruncated ? "+" : ""})`}
            color="var(--color-text-muted)"
          />

          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={clearFilters}
              style={{
                ...btnGhost, padding: "6px 10px", fontSize: 11,
              }}
            >
              <X size={11} />
              Clear ({activeFilterCount})
            </button>
          )}
        </div>
      </div>

      {/* ── Status line ── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 8, fontSize: 11, color: "var(--color-text-faint)",
      }}>
        <span>
          Showing {rows.length.toLocaleString()} of{" "}
          {(hitsTotal + filteredMega.length).toLocaleString()}
          {(loadingDb || loadingMega) && (
            <span style={{ marginLeft: 8, color: lime, display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Loader2 size={11} className="spin" /> loading…
            </span>
          )}
        </span>
        {megaScannedAt && (
          <span title={`MEGA bucket scan completed ${megaScannedAt}`}>
            MEGA scanned: {new Date(megaScannedAt).toLocaleString()}
          </span>
        )}
      </div>

      {(dbError || megaError) && (
        <div style={{
          background: "color-mix(in srgb, var(--color-danger) 12%, transparent)",
          border: "1px solid var(--color-danger)",
          borderRadius: 8, padding: "8px 12px", marginBottom: 10,
          fontSize: 12, color: "var(--color-text)",
        }}>
          {dbError && <div>Search: {dbError}</div>}
          {megaError && <div>MEGA scan: {megaError}</div>}
        </div>
      )}

      {/* ── Results table ── */}
      <div style={{
        border: "1px solid var(--color-border)",
        borderRadius: 10,
        overflow: "hidden",
        background: "var(--color-surface)",
      }}>
        {rows.length === 0 ? (
          <div style={{
            padding: "40px 20px", textAlign: "center",
            color: "var(--color-text-faint)", fontSize: 13,
          }}>
            {loadingDb || loadingMega
              ? "Searching paperwork…"
              : query || activeFilterCount > 0
                ? "No paperwork matches these filters."
                : "No paperwork on file yet."}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{
                  background: "var(--color-elevated)",
                  color: "var(--color-text-muted)",
                  textAlign: "left",
                  fontSize: 10,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}>
                  <Th style={{ width: 90 }}>Date</Th>
                  <Th style={{ width: 70 }}>Studio</Th>
                  <Th style={{ width: 90 }}>Scene</Th>
                  <Th>Talent</Th>
                  <Th style={{ width: 60 }}>Role</Th>
                  <Th>Document</Th>
                  <Th style={{ width: 80, textAlign: "right" }}>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => (
                  <RowView
                    key={r.source === "db" ? `db-${r.hit.id}` : `mega-${r.file.key}`}
                    row={r}
                    zebra={idx % 2 === 1}
                    onOpenDb={(id) => setEditingId(id)}
                    onOpenMega={openMegaFile}
                    onRenameMega={startRename}
                    pdfUrl={(id, asOf) => client.compliance.signaturePdfUrl(id, asOf ? { asOf } : undefined)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Rename modal (MEGA file rename) ── */}
      {renameTarget && (
        <RenameDialog
          target={renameTarget}
          draft={renameDraft}
          setDraft={setRenameDraft}
          running={renaming}
          error={renameError}
          onCancel={() => { setRenameTarget(null); setRenameError(null) }}
          onConfirm={commitRename}
        />
      )}

      {/* ── Edit modal (DB rows only) ── */}
      {editingId !== null && (
        <SignatureEditModal
          signatureId={editingId}
          idToken={idToken}
          onClose={() => setEditingId(null)}
          onSaved={() => { void loadDb({ silent: true }) }}
        />
      )}

      {/* Spin keyframes — a couple of icons reuse the existing app spin class
          name, but the component is rendered in pages that don't always have
          it in scope, so we declare it locally to be safe. */}
      <style jsx>{`
        :global(.spin) { animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}

// ─── Row ─────────────────────────────────────────────────────────────────────

function RowView({
  row, zebra, onOpenDb, onOpenMega, onRenameMega, pdfUrl,
}: {
  row: Row
  zebra: boolean
  onOpenDb: (id: number) => void
  onOpenMega: (f: MegaLegalFile) => void
  onRenameMega: (f: MegaLegalFile) => void
  pdfUrl: (id: number, asOf?: string) => string
}) {
  const cellStyle: React.CSSProperties = {
    padding: "8px 10px",
    borderBottom: "1px solid var(--color-border)",
    color: "var(--color-text)",
    verticalAlign: "top",
  }
  const bg = zebra ? "var(--color-bg)" : "transparent"

  if (row.source === "db") {
    const h = row.hit
    const code = studioCode(h.studio)
    const color = studioColor(h.studio)
    return (
      <tr
        style={{ background: bg, cursor: "pointer" }}
        onClick={() => onOpenDb(h.id)}
        title="Open paperwork record"
      >
        <td style={cellStyle}>
          <div style={{ fontWeight: 600 }}>
            {h.shoot_date || "—"}
          </div>
        </td>
        <td style={cellStyle}>
          <span style={{
            display: "inline-block",
            padding: "1px 6px",
            borderRadius: 4,
            background: `color-mix(in srgb, ${color} 20%, transparent)`,
            color,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.06em",
          }}>
            {code || h.studio || "—"}
          </span>
        </td>
        <td style={{ ...cellStyle, fontFamily: "var(--font-mono, ui-monospace, monospace)", fontSize: 11 }}>
          {h.scene_id || "—"}
        </td>
        <td style={cellStyle}>
          <div style={{ fontWeight: 600 }}>{h.talent_display}</div>
          <div style={{ color: "var(--color-text-faint)", fontSize: 11 }}>
            {h.legal_name}
            {h.stage_names && h.stage_names !== h.legal_name && (
              <span> · aka {h.stage_names}</span>
            )}
          </div>
        </td>
        <td style={cellStyle}>
          <span style={{
            color: h.talent_role === "female"
              ? "var(--color-pink, #ec4899)"
              : "var(--color-blue, #3b82f6)",
            fontSize: 11,
            fontWeight: 600,
            textTransform: "capitalize",
          }}>
            {h.talent_role}
          </span>
        </td>
        <td style={cellStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <FileText size={12} color="var(--color-lime)" />
            <span style={{ fontSize: 11 }}>Agreement + W-9 + 2257</span>
          </div>
          <div style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
            TIN ····{h.tin_last4 || "—"} · {h.tin_type?.toUpperCase()}
          </div>
        </td>
        <td style={{ ...cellStyle, textAlign: "right", whiteSpace: "nowrap" }}>
          <a
            href={pdfUrl(h.id)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            style={btnTinyLink}
            title="Render signed PDF in a new tab"
          >
            <ExternalLink size={11} /> PDF
          </a>
        </td>
      </tr>
    )
  }

  // MEGA-only row — paperwork that lives on the bucket but doesn't have a
  // structured compliance_signatures row yet. We show a "Not imported"
  // pill so the operator knows this is the artifact-only state, and try to
  // pull the talent name out of the filename so the row isn't anonymous.
  const f = row.file
  const color = studioColor(f.studio)
  const guessedTalent = guessTalentFromFilename(f.filename)
  const docKind = classifyDocument(f.filename)
  return (
    <tr
      style={{ background: bg, cursor: "pointer" }}
      onClick={() => onOpenMega(f)}
      title="MEGA file — not yet imported into the records DB. Click to download."
    >
      <td style={cellStyle}>
        <div style={{ fontWeight: 600, color: "var(--color-text-muted)" }}>
          {(f.last_modified || "").slice(0, 10) || "—"}
        </div>
        <div style={{
          fontSize: 9, color: "var(--color-text-faint)",
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          MEGA
        </div>
      </td>
      <td style={cellStyle}>
        <span style={{
          display: "inline-block",
          padding: "1px 6px",
          borderRadius: 4,
          background: `color-mix(in srgb, ${color} 20%, transparent)`,
          color,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.06em",
        }}>
          {f.studio}
        </span>
      </td>
      <td style={{ ...cellStyle, fontFamily: "var(--font-mono, ui-monospace, monospace)", fontSize: 11 }}>
        {f.scene_id || "—"}
      </td>
      <td style={cellStyle}>
        {guessedTalent ? (
          <>
            <div style={{ fontWeight: 600 }}>{guessedTalent}</div>
            <div style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
              From filename
            </div>
          </>
        ) : (
          <span style={{ color: "var(--color-text-faint)", fontSize: 11 }}>
            —
          </span>
        )}
      </td>
      <td style={cellStyle}>
        <span style={{
          display: "inline-block",
          padding: "1px 6px",
          borderRadius: 4,
          border: "1px solid var(--color-border)",
          color: "var(--color-text-faint)",
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}>
          Not imported
        </span>
      </td>
      <td style={cellStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <HardDrive size={12} color="var(--color-text-faint)" />
          <span style={{ fontSize: 11, wordBreak: "break-all" }}>{f.filename}</span>
        </div>
        <div style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
          {docKind} · {formatBytes(f.size)}
        </div>
      </td>
      <td style={{ ...cellStyle, textAlign: "right", whiteSpace: "nowrap" }}>
        <div style={{ display: "inline-flex", gap: 4 }}>
          <button
            type="button"
            onClick={e => { e.stopPropagation(); onRenameMega(f) }}
            style={btnTinyLink}
            title="Rename this file on MEGA — COPY then DELETE, cannot be undone"
            aria-label="Rename file"
          >
            <Pencil size={11} />
          </button>
          <button
            type="button"
            onClick={e => { e.stopPropagation(); onOpenMega(f) }}
            style={btnTinyLink}
            title="Generate a presigned download URL"
          >
            <Download size={11} /> Open
          </button>
        </div>
      </td>
    </tr>
  )
}

// ─── Filename heuristics ─────────────────────────────────────────────────────

/**
 * Best-effort extract a talent display name from a MEGA legal-folder
 * filename. Handles three observed conventions:
 *
 *   1. CamelCase from the prepare flow: `JadaSnow-061220.pdf` → "Jada Snow"
 *   2. Two-word lowercase/mixed: `mike mancini oct 5 2019.pdf` → "Mike Mancini"
 *   3. Two-word with date suffix: `Marilyn Johnson 121822.pdf` → "Marilyn Johnson"
 *
 * Returns null when no name can be confidently extracted (e.g. raw
 * timestamp filenames like `20190707_101817.jpg`).
 */
function guessTalentFromFilename(filename: string): string | null {
  const stem = filename.replace(/\.[^.]+$/, "")        // drop extension

  // Pattern 1: CamelCase head (e.g. "JadaSnow-061220" → "JadaSnow")
  const head = stem.split(/[-_ ]/, 1)[0] || ""
  if (/^[A-Z][a-z]+([A-Z][a-z]+)+$/.test(head)) {
    const NON_NAMES = new Set([
      "SignedAgreement", "SignedRelease", "ReleaseOriginal", "ModelRelease",
      "Disclosure", "Performer", "Custom", "Original", "Document", "Photo",
    ])
    if (!NON_NAMES.has(head)) {
      return head.replace(/([a-z])([A-Z])/g, "$1 $2")
    }
  }

  // Pattern 2/3: leading word(s) before a date / number / known suffix.
  // Take up to the first occurrence of: a digit, a month abbreviation, or
  // a parenthesized chunk. Then keep the first 2 alpha words as the name.
  const stop = stem.search(/\b(\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b/i)
  const lead = (stop > 0 ? stem.slice(0, stop) : stem).trim()
  // Words separated by spaces / underscores / hyphens, alpha only
  const words = lead.split(/[\s_\-]+/).filter(w => /^[a-zA-Z'\.]+$/.test(w))
  if (words.length < 2) return null
  const name = words.slice(0, 2)
    .map(w => w[0].toUpperCase() + w.slice(1).toLowerCase())
    .join(" ")
  // Reject obvious non-names
  const REJECT = /^(Signed|Agreement|Release|Disclosure|W ?9|2257|Mike Manicini|Custom Field|Test File)$/i
  if (REJECT.test(name)) return null
  // First word must look like a real first name (≥3 letters, not all-caps acronym)
  if (words[0].length < 2) return null
  return name
}

/**
 * Coarse classification of a legacy paperwork file based on its filename.
 * Drives the "Document" subtitle on MEGA rows so the operator knows what
 * they're about to download before opening it.
 */
function classifyDocument(filename: string): string {
  const lower = filename.toLowerCase()
  if (/(2257|disclosure)/.test(lower))                  return "2257 disclosure"
  if (/w-?9/.test(lower))                                return "W-9"
  if (/(agreement|release|contract)/.test(lower))        return "Agreement"
  if (/(bunny.?ear)/.test(lower))                        return "Verification photo"
  if (/(front|back|id|license|passport)/.test(lower))    return "ID photo"
  if (lower.endsWith(".pdf"))                            return "PDF"
  if (/\.(jpe?g|png|heic|webp)$/i.test(lower))           return "Photo"
  return "File"
}

// ─── Tiny presentational helpers ─────────────────────────────────────────────

// Modal dialog for renaming a MEGA legal file. Destructive operation —
// the body explains COPY + DELETE so admins know there's no undo.
function RenameDialog({
  target, draft, setDraft, running, error, onCancel, onConfirm,
}: {
  target: MegaLegalFile
  draft: string
  setDraft: (s: string) => void
  running: boolean
  error: string | null
  onCancel: () => void
  onConfirm: () => void
}) {
  const oldExt = (target.filename.match(/\.[^.]+$/) || [""])[0]
  const newKey = target.key.replace(/[^/]+$/, draft.trim() || target.filename)

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="rename-title"
      onClick={onCancel}
      style={{
        position: "fixed", inset: 0,
        background: "rgba(0,0,0,0.6)", zIndex: 50,
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 12,
          padding: "20px 22px",
          width: "min(560px, 100%)",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <Pencil size={14} color="var(--color-lime)" />
          <h3
            id="rename-title"
            style={{
              margin: 0, fontSize: 13, fontWeight: 700,
              letterSpacing: "0.04em", textTransform: "uppercase",
              color: "var(--color-text)",
            }}
          >
            Rename MEGA file
          </h3>
        </div>
        <p style={{
          margin: "0 0 14px", fontSize: 11,
          color: "var(--color-text-faint)", lineHeight: 1.55,
        }}>
          {target.studio} / {target.scene_id}
        </p>

        <label style={{ display: "block", fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
          Current filename
        </label>
        <div style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 12, color: "var(--color-text-muted)",
          padding: "8px 10px",
          background: "var(--color-bg)",
          border: "1px solid var(--color-border)",
          borderRadius: 6, marginBottom: 12, wordBreak: "break-all",
        }}>
          {target.filename}
        </div>

        <label style={{ display: "block", fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
          New filename (must keep <code>{oldExt}</code>)
        </label>
        <input
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          autoFocus
          spellCheck={false}
          onKeyDown={e => {
            if (e.key === "Enter") { e.preventDefault(); onConfirm() }
            if (e.key === "Escape") { e.preventDefault(); onCancel() }
          }}
          style={{
            width: "100%",
            background: "var(--color-elevated)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            padding: "8px 10px",
            fontSize: 13,
            color: "var(--color-text)",
            outline: "none",
            boxSizing: "border-box",
            fontFamily: "var(--font-mono, ui-monospace, monospace)",
          }}
        />

        {/* Resulting MEGA key preview */}
        <div style={{
          fontSize: 10, color: "var(--color-text-faint)",
          marginTop: 8, marginBottom: 14,
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          wordBreak: "break-all",
        }}>
          → {newKey}
        </div>

        <div style={{
          display: "flex", alignItems: "flex-start", gap: 8,
          background: "color-mix(in srgb, var(--color-warning, #f59e0b) 14%, transparent)",
          border: "1px solid var(--color-warning, #f59e0b)",
          borderRadius: 6, padding: "8px 10px", marginBottom: 14,
        }}>
          <AlertTriangle size={13} color="var(--color-warning, #f59e0b)" style={{ marginTop: 1, flexShrink: 0 }} />
          <div style={{ fontSize: 11, color: "var(--color-text)", lineHeight: 1.5 }}>
            This does a server-side <strong>COPY</strong> to the new key, then{" "}
            <strong>DELETE</strong> on the old key. MEGA S4 has no versioning —
            once the old key is deleted, it&apos;s gone. Any signature record
            pointing at the old path is rewritten to the new one.
          </div>
        </div>

        {error && (
          <div style={{
            marginBottom: 12, padding: "6px 10px",
            background: "color-mix(in srgb, var(--color-danger) 12%, transparent)",
            border: "1px solid var(--color-danger)", borderRadius: 6,
            fontSize: 11, color: "var(--color-text)",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={running}
            style={btnGhost}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={running || !draft.trim() || draft.trim() === target.filename}
            style={{
              ...btnGhost,
              background: "color-mix(in srgb, var(--color-lime) 16%, transparent)",
              color: "var(--color-lime)",
              borderColor: "var(--color-lime)",
            }}
          >
            {running ? <Loader2 size={13} className="spin" /> : <Pencil size={13} />}
            Rename
          </button>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div>
      <div style={{
        fontSize: 9, textTransform: "uppercase", letterSpacing: "0.06em",
        color: "var(--color-text-faint)",
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 16, fontWeight: 700,
        color: highlight ? "var(--color-lime)" : "var(--color-text)",
      }}>
        {value.toLocaleString()}
      </div>
    </div>
  )
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--color-text-faint)" }}>
      <span style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
      {children}
    </label>
  )
}

function SourceChip({
  active, onToggle, label, color,
}: { active: boolean; onToggle: () => void; label: string; color: string }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      style={{
        background: active ? `color-mix(in srgb, ${color} 16%, transparent)` : "transparent",
        border: `1px solid ${active ? color : "var(--color-border)"}`,
        color: active ? color : "var(--color-text-faint)",
        borderRadius: 6,
        padding: "5px 9px",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.04em",
        cursor: "pointer",
        textTransform: "uppercase",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  )
}

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th style={{
      padding: "8px 10px",
      borderBottom: "1px solid var(--color-border)",
      fontWeight: 600,
      ...style,
    }}>
      {children}
    </th>
  )
}

function formatBytes(n: number): string {
  if (!n) return "0 B"
  const units = ["B", "KB", "MB", "GB"]
  let i = 0, v = n
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

const inputCompact: React.CSSProperties = {
  background: "var(--color-elevated)",
  border: "1px solid var(--color-border)",
  borderRadius: 6,
  padding: "5px 8px",
  fontSize: 11,
  color: "var(--color-text)",
  fontFamily: "inherit",
  outline: "none",
}

const btnGhost: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-border)",
  borderRadius: 6,
  padding: "6px 10px",
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: "var(--color-text-muted)",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  fontFamily: "inherit",
}

const btnTinyLink: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  background: "transparent",
  border: "1px solid var(--color-border)",
  borderRadius: 5,
  padding: "3px 7px",
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: "var(--color-text-muted)",
  cursor: "pointer",
  textDecoration: "none",
  fontFamily: "inherit",
}
