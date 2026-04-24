"use client"

import { useState, useEffect, useMemo } from "react"
import { Download, Wand2, Link2, RotateCcw } from "lucide-react"
import { formatApiError } from "@/lib/errors"
import { useStream } from "@/lib/sse"
import { api, API_BASE_URL, type Script, type Ticket } from "@/lib/api"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { StudioSelector, STUDIOS } from "@/components/ui/studio-selector"
import { CopyButton } from "@/components/ui/copy-button"
import { PageHeader } from "@/components/ui/page-header"
import { SheetRowModal } from "@/components/ui/sheet-row-modal"
import { TodayBriefing, type Briefing } from "@/components/ui/today-briefing"
import { studioAbbr } from "@/lib/studio-colors"
import { BatchPanel } from "./batch-panel"
const SCENE_TYPES = ["BG", "BGCP"]

// Parse structured sections from generated output
function parseSections(text: string): Record<string, string> {
  // Strip markdown bold from section headers so **THEME**: → THEME:
  const clean = text.replace(/\*\*([^*\n]+)\*\*/g, "$1")
  const SECTION_KEYS = ["THEME", "PLOT", "SHOOT LOCATION", "SET DESIGN", "PROPS", "WARDROBE - FEMALE", "WARDROBE - MALE"]
  const result: Record<string, string> = {}
  const lookahead = SECTION_KEYS.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ":").join("|")
  for (const key of SECTION_KEYS) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    const re = new RegExp(`${escaped}:([\\s\\S]*?)(?=${lookahead}|$)`, "i")
    const m = clean.match(re)
    if (m) result[key] = m[1].trim()
  }
  return result
}

interface Props {
  tabs: string[]
  tabsError: string | null
  idToken: string | undefined
  userRole?: string
  briefing?: Briefing | null
}

export function ScriptGenerator({ tabs, tabsError, idToken: serverIdToken, userRole = "editor", briefing }: Props) {
  const idToken = useIdToken(serverIdToken)
  const isAdmin = userRole === "admin"

  const [mode, setMode] = useState<"manual" | "sheet">("manual")
  const [batchMode, setBatchMode] = useState(false)

  // Manual mode fields
  const [studio, setStudio] = useState("FuckPassVR")
  const [sceneType, setSceneType] = useState("BG")
  const [female, setFemale] = useState("")
  const [male, setMale] = useState("")
  const [destination, setDestination] = useState("")
  const [directorNote, setDirectorNote] = useState("")

  // Sheet mode
  const [selectedTab, setSelectedTab] = useState(tabs[0] ?? "")
  const [sheetRows, setSheetRows] = useState<Script[]>([])
  const [sheetLoading, setSheetLoading] = useState(false)
  const [sheetError, setSheetError] = useState<string | null>(null)
  const [selectedRow, setSelectedRow] = useState<Script | null>(null)
  const [pendingRow, setPendingRow] = useState<Script | null>(null)

  // Stream
  const stream = useStream()

  // Save state
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)

  // Post-generation features
  const [violations, setViolations] = useState<string[]>([])
  const [validationRan, setValidationRan] = useState(false)
  const [genTitleText, setGenTitleText] = useState("")
  const [titleGenerating, setTitleGenerating] = useState(false)
  const [feedback, setFeedback] = useState("")
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [linkedTicket, setLinkedTicket] = useState("")

  // Parsed sections from output — memoized so regex doesn't re-run on every render
  const sections = useMemo(
    () => (stream.output ? parseSections(stream.output) : {}),
    [stream.output]
  )

  const client = api(idToken ?? null)

  // Auto-validate when stream finishes
  useEffect(() => {
    if (stream.streaming || !stream.output) return
    const s = parseSections(stream.output)
    if (!s["THEME"] && !s["PLOT"]) return
    setValidationRan(false)
    client.scripts.validate({
      theme: s["THEME"] ?? "",
      plot: s["PLOT"] ?? "",
      wardrobe_f: s["WARDROBE (F)"] ?? "",
      wardrobe_m: s["WARDROBE (M)"] ?? "",
      shoot_location: s["SHOOT LOCATION"] ?? "",
      female,
      male,
    }).then((r) => {
      setViolations(r.violations)
      setValidationRan(true)
    }).catch(() => setValidationRan(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.streaming, stream.output])

  // Load tickets for linking dropdown
  useEffect(() => {
    client.tickets.list({ status: "In Progress" }).then(setTickets).catch((e) => {
      console.warn("[scripts] Failed to load tickets for linking:", e)
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load rows when tab changes
  useEffect(() => {
    if (mode !== "sheet" || !selectedTab) return
    setSheetLoading(true)
    setSheetError(null)
    client.scripts
      .list({ tab_name: selectedTab, needs_script: true })
      .then(rows => {
        setSheetRows(rows)
        setSheetLoading(false)
      })
      .catch(e => {
        setSheetError(e instanceof Error ? e.message : "Failed to load rows")
        setSheetLoading(false)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTab, mode])

  // True if the user has typed anything in manual mode that a sheet row
  // would either overwrite (female/male/studio) or hide from view
  // (directorNote/destination — preserved across row selection, but not
  // visible in sheet mode, so we warn before the view shift).
  const manualIsDirty = useMemo(
    () => female !== "" || male !== "" || directorNote !== "" || destination !== "",
    [female, male, directorNote, destination]
  )

  /**
   * Populate manual fields from a sheet row.
   * Overwrites: selectedRow, studio, female, male.
   * Preserves:  directorNote, destination, sceneType, feedback, stream output.
   * Callers must route through selectRow() so the dirty-check fires.
   */
  function applyRow(row: Script) {
    setSelectedRow(row)
    setStudio(row.studio || "FuckPassVR")
    setFemale(row.female || "")
    setMale(row.male || "")
    setPendingRow(null)
    setMode("manual")
  }

  function selectRow(row: Script) {
    // Row selection clobbers studio/female/male. Warn if any of those
    // three would meaningfully change AND the user has typed anything
    // manually. directorNote/destination are preserved by applyRow, so
    // they flag dirtiness but don't gate the overwrite check.
    const wouldOverwrite =
      (row.female || "") !== female ||
      (row.male || "") !== male ||
      (row.studio || "FuckPassVR") !== studio
    if (manualIsDirty && wouldOverwrite) {
      setPendingRow(row)
      return
    }
    applyRow(row)
  }

  /**
   * Guarded mode switch — when moving from manual to sheet with dirty
   * inputs, surface a confirmation so the user knows their manual state
   * is preserved (just hidden) and doesn't assume they've lost work.
   */
  function switchMode(next: "manual" | "sheet") {
    if (mode === next) return
    if (mode === "manual" && next === "sheet" && manualIsDirty) {
      const ok = window.confirm(
        "Your manual inputs will be hidden while you browse sheet rows. They'll still be there when you return — continue?",
      )
      if (!ok) return
    }
    setMode(next)
  }

  function generate() {
    stream.start(
      `${API_BASE_URL}/api/scripts/generate`,
      idToken,
      {
        studio,
        scene_type: sceneType,
        female,
        male,
        destination: studio === "FuckPassVR" ? destination : undefined,
        director_note: directorNote || undefined,
        tab_name: selectedRow?.tab_name,
        sheet_row: selectedRow?.sheet_row,
      }
    )
  }

  async function save() {
    if (!stream.output || !selectedRow) return
    if (violations.length > 0) {
      const ok = window.confirm(
        `This script has ${violations.length} validation issue${violations.length === 1 ? "" : "s"}. Save anyway?`,
      )
      if (!ok) return
    }
    setSaving(true)
    setSaveMsg(null)
    try {
      await client.scripts.save({
        tab_name: selectedRow.tab_name,
        sheet_row: selectedRow.sheet_row,
        theme: sections["THEME"] ?? "",
        plot: sections["PLOT"] ?? "",
        wardrobe_f: sections["WARDROBE (F)"],
        wardrobe_m: sections["WARDROBE (M)"],
        shoot_location: sections["SHOOT LOCATION"],
        props: "",
      })
      setSaveMsg("Saved to sheet.")
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save"))
    } finally {
      setSaving(false)
    }
  }

  async function submitForApproval() {
    if (!stream.output) return
    if (violations.length > 0) {
      setSaveMsg(`Can't submit — ${violations.length} validation issue${violations.length === 1 ? "" : "s"} must be resolved first.`)
      return
    }
    setSaving(true)
    setSaveMsg(null)
    try {
      await client.approvals.create({
        scene_id: selectedRow?.id?.toString() ?? female.replace(/\s+/g, "-"),
        studio,
        content_type: "script",
        content_json: JSON.stringify(sections),
        notes: linkedTicket ? `Linked: ${linkedTicket}` : "",
        target_sheet: selectedRow?.tab_name,
        target_range: selectedRow ? `G${selectedRow.sheet_row}` : "",
      })
      setSaveMsg("Submitted for approval.")
    } catch (e) {
      setSaveMsg(formatApiError(e, "Submit"))
    } finally {
      setSaving(false)
    }
  }

  async function generateScriptTitle() {
    setTitleGenerating(true)
    try {
      const { title } = await client.scripts.generateTitle({
        studio,
        female,
        theme: sections["THEME"] ?? "",
        plot: sections["PLOT"] ?? "",
      })
      setGenTitleText(title)
    } catch {
      setGenTitleText("")
    } finally {
      setTitleGenerating(false)
    }
  }

  function downloadTxt() {
    if (!stream.output) return
    const blob = new Blob([stream.output], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${studio}_${female.replace(/\s+/g, "_")}_${sceneType}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  function regenerateWithFeedback() {
    stream.start(
      `${API_BASE_URL}/api/scripts/generate`,
      idToken,
      {
        studio,
        scene_type: sceneType,
        female,
        male,
        destination: studio === "FuckPassVR" ? destination : undefined,
        director_note: feedback || undefined,
        tab_name: selectedRow?.tab_name,
        sheet_row: selectedRow?.sheet_row,
      }
    )
    setFeedback("")
    setViolations([])
    setValidationRan(false)
    setGenTitleText("")
  }

  const studioColor = STUDIO_COLOR[studio] ?? "var(--color-text-muted)"

  // Cmd+Enter to generate, Cmd+S to save
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault()
        if (!stream.streaming && female) generate()
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault()
        if (!stream.streaming && stream.output && selectedRow && !saving) save()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.streaming, stream.output, female, selectedRow, saving])

  // V2 header derived state — stats for the eyebrow/subtitle ribbon.
  const queueLabel = mode === "sheet"
    ? (sheetLoading ? "loading tabs…" : selectedTab ? `${sheetRows.length} need scripts in ${selectedTab}` : `${tabs.length} tabs available`)
    : female ? `${female}${male ? ` / ${male}` : ""} — ${sceneType}` : "awaiting talent"
  const outputStats = stream.output
    ? (() => {
        const words = stream.output.split(/\s+/).filter(Boolean).length
        const mins = Math.max(1, Math.round(words / 150))
        return `${words.toLocaleString()} words · ~${mins} min read${stream.streaming ? " · streaming" : ""}`
      })()
    : (stream.streaming ? "streaming…" : "no output yet")

  return (
    <div>
      <PageHeader
        title="Scripts"
        eyebrow={`WRITING ROOM · ${mode === "manual" ? "MANUAL" : "FROM SHEET"} · ${studioAbbr(studio)}`}
        subtitle={queueLabel}
        studioAccent={studio}
        actions={
          <div
            className="ec-seg"
            role="tablist"
            aria-label="Scripts input mode"
            style={{
              display: "inline-flex",
              border: "1px solid var(--color-border)",
              background: "var(--color-surface)",
              borderRadius: 4,
              overflow: "hidden",
            }}
          >
            {(["manual", "sheet"] as const).map(m => {
              const active = mode === m
              const showDirtyDot = m === "manual" && mode !== "manual" && manualIsDirty
              return (
                <button
                  key={m}
                  role="tab"
                  aria-selected={active}
                  onClick={() => switchMode(m)}
                  title={showDirtyDot ? "You have unsaved manual inputs" : undefined}
                  style={{
                    padding: "6px 14px",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    background: active ? "var(--color-text)" : "transparent",
                    color: active ? "var(--color-base)" : "var(--color-text-muted)",
                    border: "none",
                    borderRight: m === "manual" ? "1px solid var(--color-border)" : undefined,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  {m === "manual" ? "Manual" : "From Sheet"}
                  {showDirtyDot && (
                    <span
                      aria-hidden="true"
                      style={{
                        display: "inline-block",
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: "var(--color-lime)",
                      }}
                    />
                  )}
                </button>
              )
            })}
          </div>
        }
      />
      {briefing && <TodayBriefing briefing={briefing} />}
      <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
        {/* Left panel — inputs. Mode tabs moved into PageHeader actions (V2). */}
        <div style={{ width: 300, flexShrink: 0 }}>
        {mode === "sheet" ? (
          <div>
            {tabsError && (
              <p style={{ fontSize: 12, color: "var(--color-err)", marginBottom: 8 }}>{tabsError}</p>
            )}
            {/* Tab selector + batch toggle */}
            <div className="mb-3">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Month tab</label>
                <label
                  title="Pick N rows, generate them all, then review Accept/Skip one at a time"
                  style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 10, color: "var(--color-text-muted)", cursor: "pointer" }}
                >
                  <input
                    type="checkbox"
                    checked={batchMode}
                    onChange={e => setBatchMode(e.target.checked)}
                    style={{ accentColor: "var(--color-lime)" }}
                  />
                  Batch
                </label>
              </div>
              <select
                value={selectedTab}
                onChange={e => { setSelectedTab(e.target.value); setSelectedRow(null) }}
                className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              >
                {tabs.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            {/* Overwrite confirmation is now handled by SheetRowModal, mounted
                at the bottom of the component. The old inline yellow banner
                would get lost when the picker list scrolled. */}
            {sheetLoading && (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Loading…</p>
            )}
            {sheetError && (
              <p style={{ fontSize: 12, color: "var(--color-err)" }}>{sheetError}</p>
            )}
            {!sheetLoading && !sheetError && sheetRows.length === 0 && (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No rows need scripts.</p>
            )}
            {!sheetLoading && sheetRows.length > 0 && batchMode && (
              <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 6 }}>
                {sheetRows.length} row{sheetRows.length === 1 ? "" : "s"} — pick in the batch panel →
              </p>
            )}
            {!sheetLoading && sheetRows.length > 0 && !batchMode && (
              <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
                {sheetRows.map((row, i) => (
                  <button
                    key={row.id}
                    onClick={() => selectRow(row)}
                    className="w-full text-left px-3 py-2 transition-colors hover:bg-[--color-elevated]"
                    style={{
                      borderBottom: i < sheetRows.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
                      background: selectedRow?.id === row.id ? "var(--color-elevated)" : undefined,
                    }}
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
                        {row.shoot_date || "—"}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          color: STUDIO_COLOR[row.studio] ?? "var(--color-text-muted)",
                          fontWeight: 600,
                        }}
                      >
                        {row.studio}
                      </span>
                    </div>
                    <p style={{ fontSize: 11, color: "var(--color-text)", marginTop: 1 }}>
                      {row.female || "—"} {row.male ? `/ ${row.male}` : ""}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Studio */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio</label>
              <StudioSelector value={studio} onChange={setStudio} />
            </div>

            {/* Scene type */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Scene type</label>
              <div className="flex gap-1">
                {SCENE_TYPES.map(t => (
                  <button
                    key={t}
                    onClick={() => setSceneType(t)}
                    className="px-2.5 py-1 rounded text-xs transition-colors"
                    style={{
                      background: sceneType === t ? "var(--color-elevated)" : "transparent",
                      color: sceneType === t ? "var(--color-text)" : "var(--color-text-muted)",
                      border: `1px solid ${sceneType === t ? "var(--color-border)" : "transparent"}`,
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Female */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Female talent</label>
              <input
                type="text"
                value={female}
                onChange={e => setFemale(e.target.value)}
                placeholder="e.g. Lilly Bell"
                className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
              <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 3 }}>Stage name — used in script header and title generation</p>
            </div>

            {/* Male */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Male talent</label>
              <input
                type="text"
                value={male}
                onChange={e => setMale(e.target.value)}
                placeholder="e.g. Seth Gamble"
                className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
            </div>

            {/* Destination — FPVR only */}
            {studio === "FuckPassVR" && (
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Destination</label>
                <input
                  type="text"
                  value={destination}
                  onChange={e => setDestination(e.target.value)}
                  placeholder="e.g. Paris, Tokyo…"
                  className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
              </div>
            )}

            {/* Director note */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Director's note <span style={{ color: "var(--color-text-faint)" }}>(optional)</span></label>
              <textarea
                value={directorNote}
                onChange={e => setDirectorNote(e.target.value)}
                rows={3}
                placeholder="Any special direction, vibe, or constraints…"
                className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
            </div>
          </div>
        )}

        {/* Generate button — lime fill reserved for the armed state.
            Inert state uses an outlined-faint treatment so users can tell
            at a glance whether a click will do anything. */}
        {(() => {
          const inert = !female && mode === "manual" && !stream.streaming
          return (
            <button
              onClick={generate}
              disabled={stream.streaming || (!female && mode === "manual")}
              className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
              style={{
                background: stream.streaming
                  ? "var(--color-elevated)"
                  : inert
                    ? "transparent"
                    : "var(--color-lime)",
                color: stream.streaming
                  ? "var(--color-text-muted)"
                  : inert
                    ? "var(--color-text-faint)"
                    : "var(--color-lime-ink)",
                border: inert ? "1px solid var(--color-border)" : "1px solid transparent",
                cursor: stream.streaming ? "wait" : inert ? "not-allowed" : "pointer",
              }}
            >
              {stream.streaming
                ? "Generating…"
                : inert
                  ? "Add female talent to continue"
                  : "Generate Script"}
            </button>
          )
        })()}

        {stream.streaming && (
          <button
            onClick={stream.stop}
            className="w-full mt-2 px-3 py-1.5 rounded text-xs transition-colors"
            style={{
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
            }}
          >
            Stop
          </button>
        )}
      </div>

      {/* Right panel — output (V2 ec-block frame) */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {mode === "sheet" && batchMode ? (
          <BatchPanel
            rows={sheetRows}
            idToken={idToken}
            isAdmin={isAdmin}
          />
        ) : (
        <section
          className="ec-block"
          style={{
            border: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            borderRadius: 4,
          }}
        >
          <header
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "9px 16px",
              borderBottom: "1px solid var(--color-border)",
            }}
          >
            <h2
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 8,
                fontFamily: "var(--font-sans)",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: "var(--color-text-muted)",
                margin: 0,
              }}
            >
              <span
                className="num"
                style={{
                  fontWeight: 800,
                  fontSize: 16,
                  letterSpacing: "-0.02em",
                  color: "var(--color-text)",
                }}
              >
                {studioAbbr(studio)}
              </span>
              Output
            </h2>
            <div
              className="act"
              style={{
                display: "flex",
                gap: 12,
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--color-text-muted)",
                alignItems: "center",
              }}
            >
              <span>{outputStats}</span>
              {!stream.streaming && stream.output && (
                <CopyButton text={stream.output} label="Copy" />
              )}
            </div>
          </header>

          <div style={{ padding: "14px 16px" }}>
        {/* Stream error */}
        {stream.error && <ErrorAlert className="mb-3">{stream.error}</ErrorAlert>}

        {!stream.output && !stream.streaming && (
          <div
            className="rounded flex flex-col items-center justify-center gap-2"
            style={{
              height: 200,
              border: "1px dashed var(--color-border)",
              color: "var(--color-text-faint)",
              fontSize: 12,
              textAlign: "center",
              padding: "0 24px",
            }}
          >
            <span style={{ fontSize: 18, opacity: 0.4 }}>◈</span>
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", fontSize: 13 }}>No script queued</span>
            <span>Pick a studio, enter talent, and hit Generate — the script streams here.</span>
          </div>
        )}

        {(stream.output || stream.streaming) && (
          <>
            {/* Beats counter when sections parsed — rest of the stat strip
                lives in the ec-block header now. */}
            {stream.output && Object.keys(sections).length > 0 && (
              <div className="flex items-center gap-3 mb-2" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                <span className="tabular-nums">{Object.keys(sections).length} beat{Object.keys(sections).length === 1 ? "" : "s"}</span>
              </div>
            )}

            {/* Raw streaming output */}
            <div
              className="rounded mb-4 overflow-auto"
              style={{
                background: "var(--color-base)",
                border: "1px solid var(--color-border-subtle)",
                padding: "12px 14px",
                maxHeight: 400,
              }}
            >
              <pre
                style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: "var(--color-text)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  margin: 0,
                }}
              >
                {stream.output}
                {stream.streaming && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 6,
                      height: 12,
                      background: studioColor,
                      marginLeft: 2,
                      verticalAlign: "middle",
                      animation: "streamCursorPulse 1s ease-in-out infinite",
                    }}
                  />
                )}
              </pre>
            </div>

            {/* Primary actions — immediately after output so user doesn't need to scroll */}
            {!stream.streaming && stream.output && (
              <div className="flex flex-col gap-3 mb-4">
                {/* Action buttons row */}
                <div className="flex items-center gap-2 flex-wrap">
                  {isAdmin ? (() => {
                    const inert = !selectedRow && !saving
                    return (
                      <button
                        onClick={save}
                        disabled={saving || !selectedRow}
                        className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                        title={inert ? "Select a sheet row to enable saving" : undefined}
                        style={{
                          background: saving ? "var(--color-elevated)" : inert ? "transparent" : "var(--color-lime)",
                          color: saving ? "var(--color-text-muted)" : inert ? "var(--color-text-faint)" : "var(--color-lime-ink)",
                          border: inert ? "1px solid var(--color-border)" : "1px solid transparent",
                          cursor: saving ? "wait" : inert ? "not-allowed" : "pointer",
                        }}
                      >
                        {saving ? "Saving..." : "Accept & Save"}
                      </button>
                    )
                  })() : (
                    <button
                      onClick={submitForApproval}
                      disabled={saving}
                      className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                      style={{
                        background: saving ? "var(--color-elevated)" : "var(--color-lime)",
                        color: saving ? "var(--color-text-muted)" : "var(--color-lime-ink)",
                        cursor: saving ? "wait" : "pointer",
                      }}
                    >
                      {saving ? "Submitting..." : "Submit for Approval"}
                    </button>
                  )}

                  <button
                    onClick={downloadTxt}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs transition-colors"
                    style={{ background: "var(--color-surface)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
                  >
                    <Download size={11} />
                    Download .txt
                  </button>

                  {saveMsg && (
                    <span style={{ fontSize: 11, color: saveMsg.includes("Saved") || saveMsg.includes("Submitted") ? "var(--color-ok)" : "var(--color-err)" }}>
                      {saveMsg}
                    </span>
                  )}
                </div>

                {/* Ticket linking */}
                {tickets.length > 0 && (
                  <div className="flex items-center gap-2">
                    <Link2 size={12} style={{ color: "var(--color-text-faint)" }} />
                    <select
                      value={linkedTicket}
                      onChange={(e) => setLinkedTicket(e.target.value)}
                      className="px-2 py-1 rounded text-xs outline-none"
                      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                    >
                      <option value="">Link to ticket...</option>
                      {tickets.map((t) => (
                        <option key={t.ticket_id} value={t.ticket_id}>
                          {t.ticket_id} — {t.title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* Parsed sections */}
            {!stream.streaming && Object.keys(sections).length > 0 && (
              <div
                className="rounded mb-4"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  overflow: "hidden",
                }}
              >
                <div
                  className="px-3 py-2"
                  style={{ borderBottom: "1px solid var(--color-border)", fontSize: 11, color: "var(--color-text-muted)", fontWeight: 500 }}
                >
                  Parsed sections
                </div>
                <div className="px-3 py-2 flex flex-col gap-3">
                  {Object.entries(sections).map(([key, val]) => (
                    <div key={key}>
                      <p style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 3 }}>
                        {key}
                      </p>
                      <p style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.6 }}>{val}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Secondary controls */}
            {!stream.streaming && stream.output && (
              <div className="flex flex-col gap-4">
                {/* Validation */}
                {validationRan && (
                  <div
                    className="rounded px-3 py-2"
                    style={{
                      background: violations.length === 0
                        ? "color-mix(in srgb, var(--color-ok) 8%, transparent)"
                        : "color-mix(in srgb, var(--color-err) 8%, transparent)",
                      border: `1px solid ${violations.length === 0
                        ? "color-mix(in srgb, var(--color-ok) 20%, transparent)"
                        : "color-mix(in srgb, var(--color-err) 20%, transparent)"}`,
                    }}
                  >
                    {violations.length === 0 ? (
                      <span style={{ fontSize: 12, color: "var(--color-ok)" }}>&#10003; Validation passed</span>
                    ) : (
                      <div>
                        <span style={{ fontSize: 12, color: "var(--color-err)", fontWeight: 600 }}>
                          {violations.length} issue{violations.length > 1 ? "s" : ""}
                        </span>
                        <ul className="mt-1 space-y-0.5">
                          {violations.map((v, i) => (
                            <li key={i} style={{ fontSize: 11, color: "var(--color-err)" }}>{v}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Title generation */}
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={generateScriptTitle}
                    disabled={titleGenerating}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors"
                    style={{
                      background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                      color: "var(--color-lime)",
                      border: "1px solid color-mix(in srgb, var(--color-lime) 25%, transparent)",
                      opacity: titleGenerating ? 0.5 : 1,
                    }}
                  >
                    <Wand2 size={11} />
                    {titleGenerating ? "Generating..." : "Generate Title"}
                  </button>
                  {genTitleText && (
                    <span
                      className="rounded px-2.5 py-1"
                      style={{ fontSize: 12, color: "var(--color-text)", background: "var(--color-elevated)", border: "1px solid var(--color-border)" }}
                    >
                      {genTitleText}
                    </span>
                  )}
                </div>

                {/* Regenerate with feedback */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Director's feedback for regeneration..."
                    className="flex-1 px-2.5 py-1.5 rounded text-xs outline-none"
                    style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                    onKeyDown={(e) => { if (e.key === "Enter" && feedback) regenerateWithFeedback() }}
                  />
                  <button
                    onClick={regenerateWithFeedback}
                    disabled={!feedback}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs transition-colors"
                    style={{
                      background: "transparent",
                      color: feedback ? "var(--color-text-muted)" : "var(--color-text-faint)",
                      border: "1px solid var(--color-border)",
                      opacity: feedback ? 1 : 0.5,
                    }}
                  >
                    <RotateCcw size={11} />
                    Regenerate
                  </button>
                </div>

                {!selectedRow && (
                  <p style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                    Select a row from "From Sheet" mode to enable saving to sheet.
                  </p>
                )}
              </div>
            )}
          </>
        )}
          </div>
        </section>
        )}
      </div>
    </div>

    {pendingRow && (
      <SheetRowModal
        row={pendingRow}
        currentFemale={female}
        currentMale={male}
        onConfirm={() => applyRow(pendingRow)}
        onCancel={() => setPendingRow(null)}
      />
    )}
    </div>
  )
}
