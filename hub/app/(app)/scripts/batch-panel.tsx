"use client"

import { useState } from "react"
import { api, API_BASE_URL, type Script } from "@/lib/api"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { formatApiError } from "@/lib/errors"

interface BatchResult {
  rowId: number
  tabName: string
  sheetRow: number
  studio: string
  female: string
  male: string
  scene: string
  label: string
  fullText: string
  fields: Record<string, string>
  violations: string[]
  autoSaved?: boolean
  dryRun?: boolean
  error?: string
}

type Decision = "accepted" | "rejected"

interface Props {
  rows: Script[]
  idToken: string | undefined
  isAdmin: boolean
  onGenerated?: () => void
}

/**
 * Streamlit parity: tab_scripts → Sheet mode → Batch toggle.
 *
 * Select N rows, optionally dry-run, run the generator sequentially,
 * then walk through the results one-by-one with Accept (save-to-Grail
 * for admins, submit-for-approval for editors) or Skip.
 */
export function BatchPanel({ rows, idToken, isAdmin, onGenerated }: Props) {
  const client = api(idToken ?? null)

  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [dryRun, setDryRun] = useState(false)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [total, setTotal] = useState(0)
  const [results, setResults] = useState<BatchResult[]>([])
  const [decisions, setDecisions] = useState<Record<number, Decision>>({})
  const [decisionSaving, setDecisionSaving] = useState<number | null>(null)
  const [decisionError, setDecisionError] = useState<string | null>(null)

  function toggleRow(id: number) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAll() {
    setSelected(new Set(rows.map(r => r.id)))
  }

  function clearSelection() {
    setSelected(new Set())
  }

  async function runBatch() {
    const targets = rows.filter(r => selected.has(r.id))
    if (targets.length === 0) return
    setRunning(true)
    setTotal(targets.length)
    setProgress(0)
    setResults([])
    setDecisions({})

    const collected: BatchResult[] = []
    for (let i = 0; i < targets.length; i++) {
      const row = targets[i]
      setProgress(i + 1)
      const label = `${row.female || "—"}${row.male ? ` / ${row.male}` : ""} — ${row.studio}`
      const sceneType = sceneTypeFor(row.studio, row.title, row.theme)

      if (dryRun) {
        collected.push({
          rowId: row.id, tabName: row.tab_name, sheetRow: row.sheet_row,
          studio: row.studio, female: row.female, male: row.male,
          scene: sceneType, label, fullText: "", fields: {}, violations: [],
          dryRun: true,
        })
        setResults([...collected])
        continue
      }

      try {
        const text = await streamOnce(
          `${API_BASE_URL}/api/scripts/generate`,
          idToken,
          {
            studio: row.studio,
            scene_type: sceneType,
            female: row.female,
            male: row.male,
            destination: row.studio === "FuckPassVR" ? "" : undefined,
            tab_name: row.tab_name,
            sheet_row: row.sheet_row,
          },
        )
        const fields = parseSections(text)
        let violations: string[] = []
        try {
          const v = await client.scripts.validate({
            theme: fields["THEME"] ?? "",
            plot: fields["PLOT"] ?? "",
            wardrobe_f: fields["WARDROBE (F)"] ?? "",
            wardrobe_m: fields["WARDROBE (M)"] ?? "",
            shoot_location: fields["SHOOT LOCATION"] ?? "",
            female: row.female,
            male: row.male,
          })
          violations = v.violations
        } catch {
          // Validation failure is non-fatal — user can still decide.
        }
        collected.push({
          rowId: row.id, tabName: row.tab_name, sheetRow: row.sheet_row,
          studio: row.studio, female: row.female, male: row.male,
          scene: sceneType, label, fullText: text, fields, violations,
        })
      } catch (e) {
        collected.push({
          rowId: row.id, tabName: row.tab_name, sheetRow: row.sheet_row,
          studio: row.studio, female: row.female, male: row.male,
          scene: sceneType, label, fullText: "", fields: {}, violations: [],
          error: e instanceof Error ? e.message : "Generation failed",
        })
      }
      setResults([...collected])
    }
    setRunning(false)
    onGenerated?.()
  }

  const reviewable = results.filter(r => !r.dryRun && !r.autoSaved)
  const nextIdx = reviewable.findIndex(r => decisions[r.rowId] === undefined && !r.error)
  const reviewed = reviewable.filter(r => decisions[r.rowId] !== undefined || r.error).length
  const current = nextIdx >= 0 ? reviewable[nextIdx] : null

  async function accept(r: BatchResult) {
    setDecisionSaving(r.rowId)
    setDecisionError(null)
    try {
      if (isAdmin) {
        await client.scripts.save({
          tab_name: r.tabName,
          sheet_row: r.sheetRow,
          theme: r.fields["THEME"] ?? "",
          plot: r.fields["PLOT"] ?? "",
          wardrobe_f: r.fields["WARDROBE (F)"],
          wardrobe_m: r.fields["WARDROBE (M)"],
          shoot_location: r.fields["SHOOT LOCATION"],
          props: "",
        })
      } else {
        await client.approvals.create({
          scene_id: String(r.rowId),
          studio: r.studio,
          content_type: "script",
          content_json: JSON.stringify(r.fields),
          notes: "Batch submission",
          target_sheet: r.tabName,
          target_range: `G${r.sheetRow}`,
        })
      }
      setDecisions(d => ({ ...d, [r.rowId]: "accepted" }))
    } catch (e) {
      setDecisionError(formatApiError(e, isAdmin ? "Save" : "Submit"))
    } finally {
      setDecisionSaving(null)
    }
  }

  function skip(r: BatchResult) {
    setDecisions(d => ({ ...d, [r.rowId]: "rejected" }))
  }

  function clearResults() {
    setResults([])
    setDecisions({})
    setProgress(0)
    setTotal(0)
    setDecisionError(null)
  }

  if (rows.length === 0) return null

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Row checklist */}
      <div
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 4,
          maxHeight: 320,
          overflow: "auto",
          background: "var(--color-surface)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "6px 10px",
            fontSize: 10,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--color-text-faint)",
            borderBottom: "1px solid var(--color-border-subtle)",
            background: "var(--color-elevated)",
          }}
        >
          <span>{selected.size} / {rows.length} selected</span>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              onClick={selectAll}
              style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 10, padding: 0 }}
            >
              All
            </button>
            <button
              type="button"
              onClick={clearSelection}
              style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 10, padding: 0 }}
            >
              None
            </button>
          </div>
        </div>
        {rows.map(row => {
          const checked = selected.has(row.id)
          const color = STUDIO_COLOR[row.studio] ?? "var(--color-text-muted)"
          return (
            <label
              key={row.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 10px",
                borderBottom: "1px solid var(--color-border-subtle)",
                cursor: "pointer",
                background: checked ? "color-mix(in srgb, var(--color-lime) 6%, transparent)" : undefined,
              }}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggleRow(row.id)}
                disabled={running}
                style={{ accentColor: "var(--color-lime)" }}
              />
              <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)", minWidth: 70 }}>
                {row.shoot_date || "—"}
              </span>
              <span style={{ fontSize: 10, fontWeight: 700, color, minWidth: 56 }}>
                {row.studio}
              </span>
              <span style={{ fontSize: 11, color: "var(--color-text)" }}>
                {row.female || "—"}{row.male ? ` / ${row.male}` : ""}
              </span>
              {row.script_status === "Done" && (
                <span style={{ marginLeft: "auto", fontSize: 9, color: "var(--color-ok)", fontWeight: 700 }}>
                  ✓ scripted
                </span>
              )}
            </label>
          )
        })}
      </div>

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--color-text-muted)", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={e => setDryRun(e.target.checked)}
            disabled={running}
            style={{ accentColor: "var(--color-lime)" }}
          />
          Dry run <span style={{ color: "var(--color-text-faint)" }}>(preview only, don&apos;t call the model)</span>
        </label>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={runBatch}
          disabled={running || selected.size === 0}
          style={{
            padding: "6px 14px",
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 700,
            background: running || selected.size === 0 ? "var(--color-elevated)" : "var(--color-lime)",
            color: running || selected.size === 0 ? "var(--color-text-muted)" : "#0d0d0d",
            border: "none",
            cursor: running || selected.size === 0 ? "not-allowed" : "pointer",
          }}
        >
          {running ? `Generating ${progress}/${total}…` : `Generate ${selected.size} Script${selected.size === 1 ? "" : "s"}`}
        </button>
      </div>

      {running && total > 0 && (
        <div style={{ height: 4, background: "var(--color-border)", borderRadius: 2, overflow: "hidden" }}>
          <div
            style={{
              width: `${(progress / total) * 100}%`,
              height: "100%",
              background: "var(--color-lime)",
              transition: "width 0.2s",
            }}
          />
        </div>
      )}

      {/* Review queue */}
      {results.length > 0 && (
        <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ display: "flex", gap: 3 }}>
              {results.map(r => {
                const dec = decisions[r.rowId]
                let color = "var(--color-elevated)"
                if (r.dryRun) color = "var(--color-text-faint)"
                else if (r.error) color = "var(--color-err)"
                else if (dec === "accepted") color = "var(--color-ok)"
                else if (dec === "rejected") color = "var(--color-err)"
                else if (current && current.rowId === r.rowId) color = "var(--color-lime)"
                return (
                  <span
                    key={r.rowId}
                    title={r.label}
                    style={{ width: 10, height: 10, borderRadius: "50%", background: color, display: "inline-block" }}
                  />
                )
              })}
            </div>
            <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              <strong style={{ color: "var(--color-text)" }}>{reviewed}</strong>/{reviewable.length} reviewed
            </span>
            <div style={{ flex: 1 }} />
            {!current && !running && (
              <button
                type="button"
                onClick={clearResults}
                style={{
                  padding: "4px 10px",
                  fontSize: 11,
                  background: "transparent",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                  borderRadius: 4,
                  cursor: "pointer",
                }}
              >
                Clear results
              </button>
            )}
          </div>

          {decisionError && (
            <div
              style={{
                padding: "6px 10px",
                borderRadius: 4,
                fontSize: 11,
                color: "var(--color-err)",
                background: "color-mix(in srgb, var(--color-err) 10%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-err) 25%, transparent)",
              }}
            >
              {decisionError}
            </div>
          )}

          {current ? (
            <ResultCard
              result={current}
              isAdmin={isAdmin}
              saving={decisionSaving === current.rowId}
              onAccept={() => accept(current)}
              onSkip={() => skip(current)}
            />
          ) : (
            !running && results.some(r => r.dryRun) && (
              <p style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                Dry run finished — {results.length} row{results.length === 1 ? "" : "s"} previewed, nothing written.
              </p>
            )
          )}

          {results.some(r => r.error) && (
            <div
              style={{
                padding: "8px 10px",
                borderRadius: 4,
                fontSize: 11,
                color: "var(--color-err)",
                background: "color-mix(in srgb, var(--color-err) 8%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-err) 20%, transparent)",
              }}
            >
              <strong>Failed rows:</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {results.filter(r => r.error).map(r => (
                  <li key={r.rowId}>{r.label} — {r.error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ─── Review card ─────────────────────────────────────────────────── */

function ResultCard({
  result, isAdmin, saving, onAccept, onSkip,
}: {
  result: BatchResult
  isAdmin: boolean
  saving: boolean
  onAccept: () => void
  onSkip: () => void
}) {
  const color = STUDIO_COLOR[result.studio] ?? "var(--color-text-muted)"
  const borderColor = result.violations.length > 0 ? "var(--color-warn)" : "var(--color-ok)"
  return (
    <div
      style={{
        border: "1px solid var(--color-border)",
        borderLeft: `3px solid ${borderColor}`,
        borderRadius: 4,
        padding: "12px 14px",
        background: "var(--color-surface)",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)" }}>{result.label}</span>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color }}>
          {result.studio}
        </span>
        {result.fields["THEME"] && (
          <span style={{ fontSize: 11, color: "var(--color-text-muted)", fontStyle: "italic" }}>
            {result.fields["THEME"]}
          </span>
        )}
      </div>

      {result.violations.length > 0 && (
        <div
          style={{
            padding: "6px 10px",
            borderRadius: 4,
            fontSize: 11,
            color: "var(--color-warn)",
            background: "color-mix(in srgb, var(--color-warn) 10%, transparent)",
            border: "1px solid color-mix(in srgb, var(--color-warn) 22%, transparent)",
          }}
        >
          ⚠️ {result.violations.join(" · ")}
        </div>
      )}

      {result.fields["PLOT"] && (
        <pre
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 12,
            lineHeight: 1.6,
            color: "var(--color-text)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            margin: 0,
            maxHeight: 220,
            overflow: "auto",
            padding: "8px 10px",
            background: "var(--color-elevated)",
            borderRadius: 4,
          }}
        >
          {result.fields["PLOT"]}
        </pre>
      )}

      {(result.fields["WARDROBE (F)"] || result.fields["WARDROBE (M)"]) && (
        <div style={{ fontSize: 10, color: "var(--color-text-muted)", display: "flex", gap: 16 }}>
          {result.fields["WARDROBE (F)"] && <span>👗 {result.fields["WARDROBE (F)"]}</span>}
          {result.fields["WARDROBE (M)"] && <span>👔 {result.fields["WARDROBE (M)"]}</span>}
        </div>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={onAccept}
          disabled={saving}
          style={{
            flex: 1,
            padding: "8px 12px",
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 700,
            background: saving ? "var(--color-elevated)" : "var(--color-lime)",
            color: saving ? "var(--color-text-muted)" : "#0d0d0d",
            border: "none",
            cursor: saving ? "wait" : "pointer",
          }}
        >
          {saving ? "Saving…" : isAdmin ? "Accept & Save" : "Submit for Approval"}
        </button>
        <button
          type="button"
          onClick={onSkip}
          disabled={saving}
          style={{
            padding: "8px 14px",
            borderRadius: 4,
            fontSize: 12,
            background: "transparent",
            color: "var(--color-text-muted)",
            border: "1px solid var(--color-border)",
            cursor: saving ? "wait" : "pointer",
          }}
        >
          👎 Skip
        </button>
      </div>
    </div>
  )
}

/* ─── Helpers ─────────────────────────────────────────────────────── */

function sceneTypeFor(studio: string, _title: string, _theme: string): string {
  if (studio === "NaughtyJOI") return "JOI"
  if (studio === "VRAllure") return "Pornstar Experience"
  return "BG"
}

/**
 * POST SSE → concatenated text. Same wire format as the useStream hook but
 * resolves once the stream closes so callers can await it sequentially.
 * 4xx responses are re-thrown — no retry, since batch operations should
 * fail fast on the bad row and keep going for the rest.
 */
async function streamOnce(url: string, token: string | undefined, body: unknown): Promise<string> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`${res.status}: ${text || "Stream failed"}`)
  }
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ""
  let out = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split("\n")
    buf = lines.pop()!
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue
      try {
        const msg = JSON.parse(line.slice(6))
        if (msg.type === "text") out += msg.text
        else if (msg.type === "error") throw new Error(msg.error)
      } catch (e) {
        if (e instanceof Error && !e.message.includes("JSON")) throw e
      }
    }
  }
  return out
}

function parseSections(text: string): Record<string, string> {
  const clean = text.replace(/\*\*([^*\n]+)\*\*/g, "$1")
  const SECTION_KEYS = ["THEME", "PLOT", "SHOOT LOCATION", "SET DESIGN", "PROPS", "WARDROBE - FEMALE", "WARDROBE - MALE"]
  const ALIASES: Record<string, string> = {
    "WARDROBE - FEMALE": "WARDROBE (F)",
    "WARDROBE - MALE":   "WARDROBE (M)",
  }
  const result: Record<string, string> = {}
  const lookahead = SECTION_KEYS.map(k => escapeRegex(k) + ":").join("|")
  for (const key of SECTION_KEYS) {
    const re = new RegExp(`${escapeRegex(key)}:([\\s\\S]*?)(?=${lookahead}|$)`, "i")
    const m = clean.match(re)
    if (m) {
      const outKey = ALIASES[key] ?? key
      result[outKey] = m[1].trim()
    }
  }
  return result
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}
