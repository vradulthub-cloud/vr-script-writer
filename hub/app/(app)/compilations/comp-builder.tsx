"use client"

import { Fragment, useState, useMemo, useEffect } from "react"
import { useStream } from "@/lib/sse"
import { api, API_BASE_URL, type Scene, type ExistingComp } from "@/lib/api"
import { StudioBadge } from "@/components/ui/studio-badge"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { StudioSelector, STUDIOS } from "@/components/ui/studio-selector"
import { PageHeader } from "@/components/ui/page-header"

type Mode = "ideas" | "builder" | "existing"

interface Props {
  allScenes: Scene[]
  scenesError: string | null
  idToken: string | undefined
}

// ---------------------------------------------------------------------------
// Parsed idea from the streaming ideas response
// ---------------------------------------------------------------------------

interface ParsedIdea {
  title: string
  concept: string
  talent: string
}

function parseIdeas(raw: string): ParsedIdea[] {
  const ideas: ParsedIdea[] = []
  // Split on blank lines or "TITLE:" to find idea blocks
  const blocks = raw.split(/\n(?=TITLE:)/g)
  for (const block of blocks) {
    const titleMatch = block.match(/TITLE:\s*(.+)/i)
    const conceptMatch = block.match(/CONCEPT:\s*(.+)/i)
    const talentMatch = block.match(/TALENT:\s*(.+)/i)
    if (titleMatch && (conceptMatch || talentMatch)) {
      ideas.push({
        title: titleMatch[1].trim(),
        concept: conceptMatch ? conceptMatch[1].trim() : "",
        talent: talentMatch ? talentMatch[1].trim() : "",
      })
    }
  }
  return ideas
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CompBuilder({ allScenes, scenesError, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [studio, setStudio] = useState("FuckPassVR")
  const [mode, setMode] = useState<Mode>("ideas")
  const [title, setTitle] = useState("")
  const [selected, setSelected] = useState<string[]>([])
  const [sceneSearch, setSceneSearch] = useState("")
  const [ideasNotes, setIdeasNotes] = useState("")
  const [ideasCount, setIdeasCount] = useState(6)

  // Existing comps state (rich shape from /compilations/existing)
  const [existingComps, setExistingComps] = useState<ExistingComp[]>([])
  const [existingLoading, setExistingLoading] = useState(false)
  const [expandedComp, setExpandedComp] = useState<string | null>(null)

  const ideasStream = useStream()
  const descStream = useStream()

  // Load existing comps when switching to that tab
  useEffect(() => {
    if (mode !== "existing") return
    setExistingLoading(true)
    client.compilations.existing(studio).then(setExistingComps).catch((e) => { console.warn("[comps] Failed to load existing:", e); setExistingComps([]) }).finally(() => setExistingLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, studio])

  const eligibleScenes = useMemo(
    () => allScenes.filter(s => s.studio === studio),
    [allScenes, studio]
  )

  const filteredScenes = useMemo(() => {
    if (!sceneSearch) return eligibleScenes
    const q = sceneSearch.toLowerCase()
    return eligibleScenes.filter(s =>
      s.title.toLowerCase().includes(q) ||
      s.performers.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q)
    )
  }, [eligibleScenes, sceneSearch])

  const selectedScenes = useMemo(
    () => allScenes.filter(s => selected.includes(s.id)),
    [allScenes, selected]
  )

  function toggleScene(id: string) {
    // Guard against a cross-studio add: a compilation is scoped to one
    // studio, so we refuse any scene whose studio doesn't match.
    const scene = allScenes.find(s => s.id === id)
    if (scene && scene.studio !== studio) {
      setSaveMsg(`Scene ${id} belongs to ${scene.studio}, not ${studio}.`)
      return
    }
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)

  // Detect volume series: given an idea title, scan existing comps whose
  // titles share a root (after stripping "Vol. N" / "Best X" suffixes) and
  // return either the next volume number or "New" when the series is fresh.
  function detectVolume(ideaTitle: string): string {
    const strip = (s: string) =>
      s.toLowerCase()
        .replace(/\bvol(?:\.|ume)?\s*\d+\b/g, "")
        .replace(/\bbest\s+(?:of\s+)?/g, "")
        .replace(/\bcompilation\b/g, "")
        .replace(/\s+/g, " ")
        .trim()
    const root = strip(ideaTitle)
    if (!root) return "New"
    const matches = existingComps.filter(c => strip(c.title) === root)
    if (matches.length === 0) return "New"
    // Find the highest "Vol. N" in matching titles and return N+1
    let maxVol = 1
    for (const c of matches) {
      const m = c.title.match(/\bvol(?:\.|ume)?\s*(\d+)\b/i)
      if (m) maxVol = Math.max(maxVol, parseInt(m[1], 10))
      else maxVol = Math.max(maxVol, 1)  // treat un-numbered as Vol. 1
    }
    return `Vol. ${maxVol + 1}`
  }

  // Parse ideas as they stream in
  const parsedIdeas = useMemo(() => {
    if (!ideasStream.output) return []
    return parseIdeas(ideasStream.output)
  }, [ideasStream.output])

  function generateIdeas() {
    setSaveMsg(null)
    ideasStream.start(
      `${API_BASE_URL}/api/compilations/ideas`,
      idToken,
      { studio, notes: ideasNotes, count: ideasCount }
    )
  }

  function generateDescription() {
    setSaveMsg(null)
    descStream.start(
      `${API_BASE_URL}/api/compilations/generate`,
      idToken,
      { studio, title: title || "", scene_ids: selected, notes: "" }
    )
  }

  function applyIdea(idea: ParsedIdea) {
    setTitle(idea.title)
    setMode("builder")
  }

  async function saveCompilation() {
    if (!descStream.output) return
    setSaving(true)
    setSaveMsg(null)
    try {
      const volume = detectVolume(title || "Untitled Compilation")
      const res = await fetch(`${API_BASE_URL}/api/compilations/save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          studio,
          title: title || "Untitled Compilation",
          scene_ids: selected,
          description: descStream.output,
          notes: "",
          status: "Draft",
          volume: volume === "New" ? "New" : volume,
        }),
      })
      if (!res.ok) throw new Error(`Save failed: ${res.status}`)
      setSaveMsg("Saved — writing to sheet.")
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const studioColor = STUDIO_COLOR[studio]

  const modeLabel = mode === "ideas" ? "Suggest Ideas" : mode === "builder" ? "Build Comp" : "Existing"

  return (
    <div>
      <PageHeader
        title="Compilations"
        eyebrow={modeLabel}
        studioAccent={studio}
        actions={
          <>
            <StudioSelector value={studio} onChange={(s) => { setStudio(s); setSelected([]) }} />
            <div
              className="flex rounded overflow-hidden"
              style={{ border: "1px solid var(--color-border)" }}
            >
              {(["ideas", "builder", "existing"] as Mode[]).map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className="px-3 py-1 text-xs transition-colors capitalize"
                  style={{
                    background: mode === m ? "var(--color-elevated)" : "transparent",
                    color: mode === m ? "var(--color-text)" : "var(--color-text-muted)",
                  }}
                >
                  {m === "ideas" ? "Suggest Ideas" : m === "builder" ? "Build Comp" : "Existing"}
                </button>
              ))}
            </div>
          </>
        }
      />

      {/* ── IDEAS MODE ── */}
      {mode === "ideas" && (
        <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
          <div style={{ width: 260, flexShrink: 0 }}>
            <div className="flex flex-col gap-3">
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                  Creative direction <span style={{ color: "var(--color-text-faint)" }}>(optional)</span>
                </label>
                <textarea
                  value={ideasNotes}
                  onChange={e => setIdeasNotes(e.target.value)}
                  rows={3}
                  placeholder="e.g. Focus on blondes, holiday theme, body type…"
                  className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 3 }}>Theme, performer type, or angle — leave blank for open-ended ideas</p>
              </div>
              {/* Ideas count slider */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                  # Ideas: <span style={{ color: "var(--color-text)" }}>{ideasCount}</span>
                </label>
                <input
                  type="range" min={3} max={10} value={ideasCount}
                  onChange={e => setIdeasCount(Number(e.target.value))}
                  className="w-full" style={{ accentColor: "var(--color-lime)" }}
                />
              </div>
              <button
                onClick={generateIdeas}
                disabled={ideasStream.streaming}
                className="w-full px-3 py-2 rounded text-xs font-semibold transition-colors"
                style={{
                  background: ideasStream.streaming ? "var(--color-elevated)" : "var(--color-lime)",
                  color: ideasStream.streaming ? "var(--color-text-muted)" : "#0d0d0d",
                  cursor: ideasStream.streaming ? "wait" : "pointer",
                }}
              >
                {ideasStream.streaming ? "Generating…" : `Suggest ${ideasCount} Ideas`}
              </button>
              {ideasStream.streaming && (
                <button
                  onClick={ideasStream.stop}
                  className="w-full px-3 py-1.5 rounded text-xs"
                  style={{ color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
                >
                  Stop
                </button>
              )}
            </div>
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            {ideasStream.error && <ErrorAlert className="mb-3">{ideasStream.error}</ErrorAlert>}

            {!ideasStream.output && !ideasStream.streaming && (
              <div
                className="rounded flex items-center justify-center"
                style={{
                  height: 180,
                  border: "1px dashed var(--color-border)",
                  color: "var(--color-text-faint)",
                  fontSize: 12,
                }}
              >
                Hit suggest and watch the ideas roll in. Pick one to start building.
              </div>
            )}

            {/* Show parsed idea cards once we have them, otherwise raw stream */}
            {ideasStream.output && parsedIdeas.length > 0 && !ideasStream.streaming ? (
              <div className="flex flex-col gap-2">
                {parsedIdeas.map((idea, i) => (
                  <div
                    key={i}
                    className="rounded px-4 py-3"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div style={{ minWidth: 0 }}>
                        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", marginBottom: 4, display: "flex", alignItems: "center", gap: 8 }}>
                          <span>{idea.title}</span>
                          {(() => {
                            const badge = detectVolume(idea.title)
                            const isNew = badge === "New"
                            return (
                              <span
                                style={{
                                  fontSize: 9,
                                  fontWeight: 600,
                                  letterSpacing: "0.04em",
                                  textTransform: "uppercase",
                                  padding: "1px 6px",
                                  borderRadius: 9,
                                  color: isNew ? "var(--color-lime)" : studioColor,
                                  background: isNew
                                    ? "color-mix(in srgb, var(--color-lime) 12%, transparent)"
                                    : `color-mix(in srgb, ${studioColor} 12%, transparent)`,
                                  border: isNew
                                    ? "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)"
                                    : `1px solid color-mix(in srgb, ${studioColor} 28%, transparent)`,
                                }}
                              >
                                {badge}
                              </span>
                            )
                          })()}
                        </p>
                        {idea.concept && (
                          <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: idea.talent ? 4 : 0 }}>
                            {idea.concept}
                          </p>
                        )}
                        {idea.talent && (
                          <p style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                            Suggested: {idea.talent}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => applyIdea(idea)}
                        className="px-3 py-1.5 rounded text-xs font-semibold shrink-0"
                        style={{
                          background: `color-mix(in srgb, ${studioColor} 15%, transparent)`,
                          color: studioColor,
                          border: `1px solid color-mix(in srgb, ${studioColor} 30%, transparent)`,
                        }}
                      >
                        Use this →
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : ideasStream.output ? (
              /* Fallback: raw stream output while streaming or if parsing fails */
              <div
                className="rounded px-4 py-3"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <pre style={{ fontSize: 12, lineHeight: 1.7, color: "var(--color-text)", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, fontFamily: "var(--font-sans)" }}>
                  {ideasStream.output}
                  {ideasStream.streaming && (
                    <span style={{ display: "inline-block", width: 6, height: 12, background: studioColor, marginLeft: 2, verticalAlign: "middle", animation: "streamCursorPulse 1s ease-in-out infinite" }} />
                  )}
                </pre>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* ── BUILDER MODE ── */}
      {mode === "builder" && (
        <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
          <div style={{ width: 340, flexShrink: 0 }}>
            <div className="flex flex-col gap-3">
              {/* Title */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                  Compilation title <span style={{ color: "var(--color-text-faint)" }}>(optional)</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="e.g. Best of 2025 — Creampies"
                  className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
              </div>

              {/* Scene search + multiselect */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                  Add scenes
                  {selected.length > 0 && (
                    <span style={{ color: studioColor, marginLeft: 6 }}>
                      {selected.length} selected
                    </span>
                  )}
                </label>
                <input
                  type="text"
                  value={sceneSearch}
                  onChange={e => setSceneSearch(e.target.value)}
                  placeholder="Search scenes…"
                  className="w-full px-2.5 py-1.5 rounded-t text-xs outline-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderBottom: "none",
                    color: "var(--color-text)",
                  }}
                />
                {scenesError ? (
                  <div className="rounded-b px-3 py-2 text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-err)" }}>
                    {scenesError}
                  </div>
                ) : (
                  <div className="rounded-b overflow-auto" style={{ border: "1px solid var(--color-border)", background: "var(--color-surface)", maxHeight: 220 }}>
                    {filteredScenes.length === 0 && (
                      <p className="px-3 py-2" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                        {sceneSearch ? "No matches." : "No scenes for this studio."}
                      </p>
                    )}
                    {filteredScenes.map((scene, i) => {
                      const isSelected = selected.includes(scene.id)
                      return (
                        <button
                          key={scene.id}
                          role="checkbox"
                          aria-checked={isSelected}
                          onClick={() => toggleScene(scene.id)}
                          className="w-full text-left px-3 py-1.5 transition-colors"
                          style={{
                            borderBottom: i < filteredScenes.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
                            background: isSelected ? `color-mix(in srgb, ${studioColor} 10%, transparent)` : "transparent",
                            display: "flex", alignItems: "center", gap: 8,
                          }}
                        >
                          <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: 3, border: `1px solid ${isSelected ? studioColor : "var(--color-border)"}`, background: isSelected ? studioColor : "transparent", flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                            {isSelected && <span style={{ fontSize: 9, color: "#000", fontWeight: 700 }}>✓</span>}
                          </span>
                          <div style={{ minWidth: 0 }}>
                            <p className="line-clamp-1" style={{ fontSize: 11, color: isSelected ? "var(--color-text)" : "var(--color-text-muted)" }}>
                              {scene.title || "Untitled"}
                            </p>
                            {scene.performers && (
                              <p style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{scene.performers}</p>
                            )}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Selected scenes list */}
              {selected.length > 0 && (
                <div>
                  <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Selected scenes</label>
                  <div className="flex flex-col gap-1">
                    {selectedScenes.map(s => (
                      <div key={s.id} className="flex items-center justify-between px-2.5 py-1.5 rounded" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                        <div>
                          <p style={{ fontSize: 11, color: "var(--color-text)" }} className="line-clamp-1">{s.title || "Untitled"}</p>
                          <p style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{s.id}</p>
                        </div>
                        <button onClick={() => toggleScene(s.id)} aria-label={`Remove ${s.title || s.id}`} style={{ fontSize: 12, color: "var(--color-text-faint)", padding: "0 4px" }}>×</button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Generate description button */}
            <button
              onClick={generateDescription}
              disabled={descStream.streaming || selected.length === 0}
              className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
              style={{
                background: descStream.streaming ? "var(--color-elevated)" : "var(--color-lime)",
                color: descStream.streaming ? "var(--color-text-muted)" : "#0d0d0d",
                cursor: descStream.streaming ? "wait" : "pointer",
                opacity: (selected.length === 0 && !descStream.streaming) ? 0.5 : 1,
              }}
            >
              {descStream.streaming ? "Generating…" : selected.length === 0 ? "Select scenes to continue" : "Generate Description"}
            </button>
            {descStream.streaming && (
              <button onClick={descStream.stop} className="w-full mt-2 px-3 py-1.5 rounded text-xs" style={{ color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}>
                Stop
              </button>
            )}
          </div>

          {/* Output */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {descStream.error && <ErrorAlert className="mb-3">{descStream.error}</ErrorAlert>}

            {!descStream.output && !descStream.streaming && (
              <div className="rounded flex items-center justify-center" style={{ height: 200, border: "1px dashed var(--color-border)", color: "var(--color-text-faint)", fontSize: 12 }}>
                Compilation description will appear here
              </div>
            )}

            {(descStream.output || descStream.streaming) && (
              <>
                <div className="rounded mb-3" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", padding: "12px 14px" }}>
                  <pre style={{ fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: 1.7, color: "var(--color-text)", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0 }}>
                    {descStream.output}
                    {descStream.streaming && (
                      <span style={{ display: "inline-block", width: 6, height: 12, background: studioColor, marginLeft: 2, verticalAlign: "middle", animation: "streamCursorPulse 1s ease-in-out infinite" }} />
                    )}
                  </pre>
                </div>

                {!descStream.streaming && descStream.output && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={saveCompilation}
                      disabled={saving}
                      className="px-3 py-1.5 rounded text-xs font-semibold"
                      style={{ background: "var(--color-lime)", color: "#0d0d0d", opacity: saving ? 0.5 : 1 }}
                    >
                      {saving ? "Saving…" : "Save Compilation"}
                    </button>
                    {saveMsg && (
                      <span style={{ fontSize: 11, color: saveMsg === "Saved." ? "var(--color-ok)" : "var(--color-err)" }}>
                        {saveMsg}
                      </span>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Existing comps tab ── */}
      {mode === "existing" && (
        <ExistingCompsTable
          comps={existingComps}
          loading={existingLoading}
          studio={studio}
          studioColor={studioColor}
          expanded={expandedComp}
          onToggle={(id) => setExpandedComp(prev => prev === id ? null : id)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Existing compilations table (sheet-synced, grouped by Comp ID)
// ---------------------------------------------------------------------------

function statusColors(status: string) {
  const s = status.trim().toLowerCase()
  if (s === "published") return { fg: "var(--color-ok)", bg: "color-mix(in srgb, var(--color-ok) 12%, transparent)", border: "color-mix(in srgb, var(--color-ok) 30%, transparent)" }
  if (s === "planned")   return { fg: "var(--color-text)",  bg: "var(--color-elevated)", border: "var(--color-border)" }
  // Draft / empty fallback
  return { fg: "var(--color-text-muted)", bg: "color-mix(in srgb, var(--color-text-muted) 10%, transparent)", border: "var(--color-border)" }
}

interface ExistingCompsTableProps {
  comps: ExistingComp[]
  loading: boolean
  studio: string
  studioColor: string
  expanded: string | null
  onToggle: (compId: string) => void
}

function ExistingCompsTable({ comps, loading, studio, studioColor, expanded, onToggle }: ExistingCompsTableProps) {
  if (loading) {
    return <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Loading existing compilations…</p>
  }
  if (comps.length === 0) {
    return (
      <div
        className="rounded flex flex-col items-center justify-center gap-2"
        style={{ height: 200, border: "1px dashed var(--color-border)", color: "var(--color-text-faint)", fontSize: 12, textAlign: "center", padding: "0 24px" }}
      >
        <span style={{ fontSize: 18, opacity: 0.4 }}>◈</span>
        <span style={{ fontWeight: 600, color: "var(--color-text-muted)", fontSize: 13 }}>No compilations yet for {studio}</span>
        <span>Build a compilation above and Save — it will appear here in the Index.</span>
      </div>
    )
  }
  return (
    <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
      <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)", width: 32 }}></th>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Comp ID</th>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Title</th>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Vol.</th>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Status</th>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Scenes</th>
            <th className="text-left px-3 py-2 font-medium" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Created</th>
          </tr>
        </thead>
        <tbody>
          {comps.map((comp) => {
            const isOpen = expanded === comp.comp_id
            const statCol = statusColors(comp.status)
            return (
              <Fragment key={comp.comp_id}>
                <tr
                  onClick={() => onToggle(comp.comp_id)}
                  style={{
                    borderBottom: "1px solid var(--color-border)",
                    cursor: "pointer",
                    background: isOpen ? "var(--color-surface)" : "transparent",
                  }}
                >
                  <td className="px-3 py-2" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                    {isOpen ? "▾" : "▸"}
                  </td>
                  <td className="px-3 py-2 font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {comp.comp_id}
                  </td>
                  <td className="px-3 py-2" style={{ fontSize: 12, color: "var(--color-text)", fontWeight: 500 }}>
                    {comp.title || <span style={{ color: "var(--color-text-faint)" }}>Untitled</span>}
                  </td>
                  <td className="px-3 py-2" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {comp.volume || "—"}
                  </td>
                  <td className="px-3 py-2" style={{ fontSize: 11 }}>
                    <span style={{
                      fontSize: 10,
                      fontWeight: 600,
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                      padding: "2px 7px",
                      borderRadius: 9,
                      color: statCol.fg,
                      background: statCol.bg,
                      border: `1px solid ${statCol.border}`,
                    }}>
                      {comp.status || "Draft"}
                    </span>
                  </td>
                  <td className="px-3 py-2" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                    {comp.scene_count}
                  </td>
                  <td className="px-3 py-2" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                    {comp.created || "—"}
                  </td>
                </tr>
                {isOpen && (
                  <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                    <td colSpan={7} className="px-4 py-3">
                      {comp.description && (
                        <div className="mb-3 rounded" style={{ background: "var(--color-elevated)", padding: "8px 10px" }}>
                          <p style={{ fontSize: 10, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Description</p>
                          <p style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{comp.description}</p>
                        </div>
                      )}
                      <p style={{ fontSize: 10, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                        Scenes (click MEGA link to download source)
                      </p>
                      <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
                        <table className="w-full" style={{ borderCollapse: "collapse" }}>
                          <thead>
                            <tr style={{ background: "var(--color-bg, var(--color-surface))" }}>
                              <th className="text-left px-2 py-1" style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 500, width: 28 }}>#</th>
                              <th className="text-left px-2 py-1" style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 500 }}>Scene ID</th>
                              <th className="text-left px-2 py-1" style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 500 }}>Title</th>
                              <th className="text-left px-2 py-1" style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 500 }}>Performers</th>
                              <th className="text-left px-2 py-1" style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 500 }}>MEGA</th>
                            </tr>
                          </thead>
                          <tbody>
                            {comp.scenes.map((sc) => (
                              <tr key={`${comp.comp_id}-${sc.scene_num}`} style={{ borderTop: "1px solid var(--color-border)" }}>
                                <td className="px-2 py-1.5" style={{ fontSize: 10, color: "var(--color-text-faint)" }}>{sc.scene_num}</td>
                                <td className="px-2 py-1.5 font-mono" style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{sc.scene_id}</td>
                                <td className="px-2 py-1.5" style={{ fontSize: 11, color: "var(--color-text)" }}>{sc.title || <span style={{ color: "var(--color-text-faint)" }}>—</span>}</td>
                                <td className="px-2 py-1.5" style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{sc.performers || "—"}</td>
                                <td className="px-2 py-1.5" style={{ fontSize: 10 }}>
                                  {sc.mega_link ? (
                                    <a
                                      href={sc.mega_link}
                                      target="_blank"
                                      rel="noreferrer"
                                      style={{ color: studioColor, textDecoration: "underline" }}
                                    >
                                      open
                                    </a>
                                  ) : (
                                    <span style={{ color: "var(--color-text-faint)" }}>pending</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 8 }}>
                        Created by {comp.created_by || "—"}
                        {comp.updated && comp.updated !== comp.created && ` · Updated ${comp.updated}`}
                      </p>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
