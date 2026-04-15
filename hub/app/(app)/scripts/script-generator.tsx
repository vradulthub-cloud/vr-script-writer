"use client"

import { useState, useEffect, useMemo } from "react"
import { useStream } from "@/lib/sse"
import { api, API_BASE_URL, type Script } from "@/lib/api"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]
const SCENE_TYPES = ["BG", "BGCP"]

// Parse structured sections from generated output
function parseSections(text: string): Record<string, string> {
  const SECTION_KEYS = ["THEME", "PLOT", "SHOOT LOCATION", "WARDROBE (F)", "WARDROBE (M)", "DIRECTOR'S NOTE"]
  const result: Record<string, string> = {}
  for (const key of SECTION_KEYS) {
    const re = new RegExp(`${key}:([\\s\\S]*?)(?=${SECTION_KEYS.map(k => k + ":").join("|")}|$)`, "i")
    const m = text.match(re)
    if (m) result[key] = m[1].trim()
  }
  return result
}

interface Props {
  tabs: string[]
  tabsError: string | null
  idToken: string | undefined
}

export function ScriptGenerator({ tabs, tabsError, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)

  const [mode, setMode] = useState<"manual" | "sheet">("manual")

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

  // Parsed sections from output — memoized so regex doesn't re-run on every render
  const sections = useMemo(
    () => (stream.output ? parseSections(stream.output) : {}),
    [stream.output]
  )

  const client = api(idToken ?? null)

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

  // True if the user has typed anything in manual mode that a sheet row would overwrite
  const manualIsDirty = useMemo(
    () => female !== "" || male !== "" || directorNote !== "",
    [female, male, directorNote]
  )

  function applyRow(row: Script) {
    setSelectedRow(row)
    setStudio(row.studio || "FuckPassVR")
    setFemale(row.female || "")
    setMale(row.male || "")
    setPendingRow(null)
    setMode("manual")
  }

  function selectRow(row: Script) {
    const wouldOverwrite =
      (row.female || "") !== female || (row.male || "") !== male
    if (manualIsDirty && wouldOverwrite) {
      setPendingRow(row)
      return
    }
    applyRow(row)
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
      })
      setSaveMsg("Saved to sheet.")
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const studioColor = STUDIO_COLOR[studio] ?? "var(--color-text-muted)"

  return (
    <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
      {/* Left panel — inputs */}
      <div style={{ width: 300, flexShrink: 0 }}>
        {/* Mode tabs */}
        <div className="flex gap-1 mb-5">
          {(["manual", "sheet"] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="px-3 py-1.5 rounded text-xs transition-colors capitalize"
              style={{
                background: mode === m ? "var(--color-elevated)" : "transparent",
                color: mode === m ? "var(--color-text)" : "var(--color-text-muted)",
                border: `1px solid ${mode === m ? "var(--color-border)" : "transparent"}`,
              }}
            >
              {m === "manual" ? "Manual" : "From Sheet"}
            </button>
          ))}
        </div>

        {mode === "sheet" ? (
          <div>
            {tabsError && (
              <p style={{ fontSize: 12, color: "var(--color-err)", marginBottom: 8 }}>{tabsError}</p>
            )}
            {/* Tab selector */}
            <div className="mb-3">
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Month tab</label>
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

            {/* Rows needing scripts */}
            {/* Overwrite confirmation — shown when a row selection would clobber manual inputs */}
            {pendingRow && (
              <div
                className="rounded mb-3"
                style={{
                  padding: "10px 12px",
                  background: "color-mix(in srgb, var(--color-warn) 10%, var(--color-surface))",
                  border: "1px solid color-mix(in srgb, var(--color-warn) 30%, transparent)",
                }}
              >
                <p style={{ fontSize: 11, color: "var(--color-warn)", marginBottom: 8, lineHeight: 1.5 }}>
                  This will overwrite your current inputs
                  {(female || male) && (
                    <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }}>
                      {" "}({[female, male].filter(Boolean).join(" / ")})
                    </span>
                  )}
                  .
                </p>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    onClick={() => applyRow(pendingRow)}
                    className="px-2.5 py-1 rounded text-xs font-medium transition-colors"
                    style={{
                      background: "color-mix(in srgb, var(--color-warn) 18%, transparent)",
                      color: "var(--color-warn)",
                      border: "1px solid color-mix(in srgb, var(--color-warn) 35%, transparent)",
                    }}
                  >
                    Overwrite
                  </button>
                  <button
                    onClick={() => setPendingRow(null)}
                    className="px-2.5 py-1 rounded text-xs transition-colors"
                    style={{
                      background: "transparent",
                      color: "var(--color-text-muted)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {sheetLoading && (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Loading…</p>
            )}
            {sheetError && (
              <p style={{ fontSize: 12, color: "var(--color-err)" }}>{sheetError}</p>
            )}
            {!sheetLoading && !sheetError && sheetRows.length === 0 && (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No rows need scripts.</p>
            )}
            {!sheetLoading && sheetRows.length > 0 && (
              <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
                {sheetRows.map((row, i) => (
                  <button
                    key={row.id}
                    onClick={() => selectRow(row)}
                    className="w-full text-left px-3 py-2 transition-colors hover:bg-[--color-elevated]"
                    style={{
                      borderBottom: i < sheetRows.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
                      background: selectedRow?.id === row.id
                        ? "var(--color-elevated)"
                        : pendingRow?.id === row.id
                          ? "color-mix(in srgb, var(--color-warn) 8%, transparent)"
                          : undefined,
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
              <div className="flex gap-1 flex-wrap">
                {STUDIOS.map(s => (
                  <button
                    key={s}
                    onClick={() => setStudio(s)}
                    className="px-2 py-1 rounded text-xs transition-colors"
                    style={{
                      background: studio === s
                        ? `color-mix(in srgb, ${STUDIO_COLOR[s]} 20%, transparent)`
                        : "transparent",
                      color: studio === s ? STUDIO_COLOR[s] : "var(--color-text-muted)",
                      border: `1px solid ${studio === s
                        ? `color-mix(in srgb, ${STUDIO_COLOR[s]} 35%, transparent)`
                        : "var(--color-border)"}`,
                    }}
                  >
                    {s === "FuckPassVR" ? "FPVR" : s === "NaughtyJOI" ? "NJOI" :
                     s === "VRHush" ? "VRH" : "VRA"}
                  </button>
                ))}
              </div>
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

        {/* Generate button */}
        <button
          onClick={generate}
          disabled={stream.streaming || (!female && mode === "manual")}
          className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
          style={{
            background: stream.streaming ? "var(--color-elevated)" : "var(--color-lime)",
            color: stream.streaming ? "var(--color-text-muted)" : "#0d0d0d",
            cursor: stream.streaming ? "wait" : "pointer",
            opacity: (!female && mode === "manual" && !stream.streaming) ? 0.5 : 1,
          }}
        >
          {stream.streaming
            ? "Generating…"
            : (!female && mode === "manual")
              ? "Add female talent to continue"
              : "Generate Script"}
        </button>

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

      {/* Right panel — output */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Stream error */}
        {stream.error && <ErrorAlert className="mb-3">{stream.error}</ErrorAlert>}

        {!stream.output && !stream.streaming && (
          <div
            className="rounded flex items-center justify-center"
            style={{
              height: 200,
              border: "1px dashed var(--color-border)",
              color: "var(--color-text-faint)",
              fontSize: 12,
            }}
          >
            Script output will appear here
          </div>
        )}

        {(stream.output || stream.streaming) && (
          <>
            {/* Raw streaming output */}
            <div
              className="rounded mb-4 overflow-auto"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                padding: "12px 14px",
                maxHeight: 400,
              }}
            >
              <pre
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
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
                      animation: "none",
                      opacity: 0.8,
                    }}
                  />
                )}
              </pre>
            </div>

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

            {/* Save button */}
            {!stream.streaming && selectedRow && (
              <div className="flex items-center gap-3">
                <button
                  onClick={save}
                  disabled={saving}
                  className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                  style={{
                    background: "var(--color-lime)",
                    color: "#0d0d0d",
                    opacity: saving ? 0.6 : 1,
                  }}
                >
                  {saving ? "Saving…" : "Save to Sheet"}
                </button>
                {saveMsg && (
                  <span style={{ fontSize: 11, color: saveMsg.includes("Saved") ? "var(--color-ok)" : "var(--color-err)" }}>
                    {saveMsg}
                  </span>
                )}
              </div>
            )}
            {!stream.streaming && !selectedRow && stream.output && (
              <p style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                Select a row from "From Sheet" mode to enable saving.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
