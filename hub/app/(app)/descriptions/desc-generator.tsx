"use client"

import { useState, useMemo, useRef, useEffect } from "react"
import { useStream } from "@/lib/sse"
import { api, API_BASE_URL, type Scene } from "@/lib/api"
import { formatApiError } from "@/lib/errors"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { StudioSelector } from "@/components/ui/studio-selector"
import { CopyButton } from "@/components/ui/copy-button"
import { PageHeader } from "@/components/ui/page-header"

// ---------------------------------------------------------------------------
// Per-studio category lists — grouped for visual structure
// ---------------------------------------------------------------------------

const STUDIO_CATEGORY_GROUPS: Record<string, { label: string; cats: string[] }[]> = {
  FuckPassVR: [
    { label: "Acts",  cats: ["Blowjob", "Cowgirl", "Reverse Cowgirl", "Creampie", "Cumshot", "Doggy Style", "Facial", "Handjob", "Missionary", "Standing Missionary"] },
    { label: "Body",  cats: ["Big Tits", "Natural Tits", "Small Tits", "Big Ass", "Petite", "Curvy", "Athletic"] },
    { label: "Look",  cats: ["Blonde", "Brunette", "Redhead", "Ebony", "Latina", "Asian"] },
    { label: "Tags",  cats: ["Teen", "Milf", "POV", "Travel", "VR Porn", "8K VR"] },
  ],
  VRHush: [
    { label: "Acts",  cats: ["Blowjob", "Cowgirl", "Reverse Cowgirl", "Creampie", "Cumshot", "Doggy Style", "Facial", "Handjob", "Missionary", "Standing Missionary"] },
    { label: "Body",  cats: ["Big Tits", "Natural Tits", "Small Tits", "Big Ass", "Petite", "Curvy", "Athletic"] },
    { label: "Look",  cats: ["Blonde", "Brunette", "Redhead", "Ebony", "Latina"] },
    { label: "Tags",  cats: ["Teen", "Milf", "American", "European", "POV", "VR Porn", "8K VR"] },
  ],
  VRAllure: [
    { label: "Acts",  cats: ["Solo", "Masturbation", "Vibrator", "Dildo", "Fingering", "Squirting"] },
    { label: "Style", cats: ["Lesbian", "Lingerie", "Striptease", "Nude"] },
    { label: "Body",  cats: ["Big Tits", "Natural Tits", "Small Tits"] },
    { label: "Look",  cats: ["Blonde", "Brunette", "Redhead", "Teen", "Milf"] },
    { label: "Tags",  cats: ["VR Porn", "8K VR"] },
  ],
  NaughtyJOI: [
    { label: "Acts",  cats: ["JOI", "Countdown", "Tease", "Instruction", "Dirty Talk", "Edging"] },
    { label: "Style", cats: ["Lingerie", "Striptease", "Solo", "Masturbation"] },
    { label: "Look",  cats: ["Blonde", "Brunette", "Natural Tits", "Small Tits"] },
    { label: "Tags",  cats: ["VR Porn"] },
  ],
}

interface Props {
  scenes: Scene[]
  scenesError: string | null
  idToken: string | undefined
  userRole?: string
}

// ---------------------------------------------------------------------------
// Inline paragraph edit component
// ---------------------------------------------------------------------------

function EditableParagraph({
  text,
  index,
  studioColor,
  onSave,
}: {
  text: string
  index: number
  studioColor: string
  onSave: (index: number, newText: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setDraft(text)
  }, [text])

  useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus()
      taRef.current.style.height = "auto"
      taRef.current.style.height = taRef.current.scrollHeight + "px"
    }
  }, [editing])

  if (editing) {
    return (
      <div className="mb-3">
        <textarea
          ref={taRef}
          value={draft}
          onChange={e => {
            setDraft(e.target.value)
            e.target.style.height = "auto"
            e.target.style.height = e.target.scrollHeight + "px"
          }}
          className="w-full px-3 py-2 rounded text-xs outline-none resize-none"
          style={{
            background: "var(--color-elevated)",
            border: `1px solid ${studioColor}`,
            color: "var(--color-text)",
            lineHeight: 1.7,
            minHeight: 60,
          }}
        />
        <div className="flex gap-2 mt-1.5">
          <button
            onClick={() => { onSave(index, draft); setEditing(false) }}
            className="px-2.5 py-1 rounded text-xs font-semibold"
            style={{ background: "var(--color-lime)", color: "#0d0d0d" }}
          >
            Save
          </button>
          <button
            onClick={() => { setDraft(text); setEditing(false) }}
            className="px-2.5 py-1 rounded text-xs"
            style={{ color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <p
      onClick={() => setEditing(true)}
      title="Click to edit"
      className="mb-3 rounded px-2 -mx-2 transition-colors cursor-text group"
      style={{
        fontSize: 13,
        color: "var(--color-text)",
        lineHeight: 1.7,
      }}
      onMouseEnter={e => (e.currentTarget.style.background = "var(--color-elevated)")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >
      {text}
    </p>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function DescGenerator({ scenes, scenesError, idToken: serverIdToken, userRole = "editor" }: Props) {
  const idToken = useIdToken(serverIdToken)
  const isAdmin = userRole === "admin"

  const [studio, setStudio] = useState("FuckPassVR")
  const [isCompilation, setIsCompilation] = useState(false)
  const [performers, setPerformers] = useState("")
  const [positions, setPositions] = useState("")
  const [selectedCats, setSelectedCats] = useState<string[]>([])
  const [keywords, setKeywords] = useState("")
  const [wardrobe, setWardrobe] = useState("")
  const [modelNotes, setModelNotes] = useState("")

  // Inline-edited paragraphs (index → edited text)
  const [editedParagraphs, setEditedParagraphs] = useState<Record<number, string>>({})

  // SEO state
  const [metaTitle, setMetaTitle] = useState("")
  const [metaDesc, setMetaDesc] = useState("")
  const [seoLoading, setSeoLoading] = useState(false)
  const [seoError, setSeoError] = useState<string | null>(null)

  // Scene picker for saving
  const [selectedSceneId, setSelectedSceneId] = useState("")

  const stream = useStream()
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [docxLoading, setDocxLoading] = useState(false)
  const [docxError, setDocxError] = useState<string | null>(null)

  const client = api(idToken ?? null)

  // Clear edits when a new generation starts
  const prevOutput = useRef("")
  useEffect(() => {
    if (stream.output !== prevOutput.current) {
      if (stream.output === "") {
        setEditedParagraphs({})
        setMetaTitle("")
        setMetaDesc("")
        setSeoError(null)
      }
      prevOutput.current = stream.output ?? ""
    }
  }, [stream.output])

  const studioScenes = useMemo(
    () => scenes.filter(s => s.studio === studio),
    [scenes, studio]
  )

  // Scenes missing descriptions — sorted by readiness
  const missingDescScenes = useMemo(() => {
    return studioScenes
      .filter(s => !s.has_description)
      .sort((a, b) => {
        const readyA = (a.title ? 1 : 0) + (a.performers ? 1 : 0) + (a.plot ? 1 : 0) + (a.categories ? 1 : 0)
        const readyB = (b.title ? 1 : 0) + (b.performers ? 1 : 0) + (b.plot ? 1 : 0) + (b.categories ? 1 : 0)
        return readyB - readyA // Most ready first
      })
  }, [studioScenes])

  const [showQueue, setShowQueue] = useState(true)
  const [grailSaving, setGrailSaving] = useState(false)

  function autoPopulateFromScene(scene: Scene) {
    setSelectedSceneId(scene.id)
    // Pre-fill every form field the Scene shape can inform. Leaves untouched
    // fields alone so a user can autopopulate, then tweak.
    if (scene.performers) setPerformers(scene.performers)
    if (scene.categories) {
      const cats = scene.categories.split(",").map(c => c.trim()).filter(Boolean)
      setSelectedCats(cats.filter(c => availableCategories.includes(c)))
    }
    if (scene.tags) {
      // Tags sit naturally in the keywords field — they're the SEO hints
      // already curated on the Grail row.
      setKeywords(scene.tags)
    }
    if (scene.theme) {
      // Theme maps to model/scene notes — it's prose-y context for the
      // description prompt, not a structured field.
      setModelNotes(scene.theme)
    }
    if (scene.title && !metaTitle) {
      // Pre-seed the SEO meta title with the scene title (user can override)
      setMetaTitle(scene.title)
    }
  }

  async function saveToGrail() {
    if (!getFullDescription() || !selectedSceneId) return
    setGrailSaving(true)
    setSaveMsg(null)
    try {
      await client.descriptions.saveGrail({
        scene_id: selectedSceneId,
        description: getFullDescription(),
        meta_title: metaTitle || undefined,
        meta_description: metaDesc || undefined,
      })
      setSaveMsg("Saved to Grail.")
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save to Grail"))
    } finally {
      setGrailSaving(false)
    }
  }

  const availableCategories = useMemo(
    () => (STUDIO_CATEGORY_GROUPS[studio] ?? []).flatMap(g => g.cats),
    [studio]
  )

  function toggleCat(cat: string) {
    setSelectedCats(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    )
  }

  // Derive paragraphs from stream output + edits
  const paragraphs = useMemo(() => {
    if (!stream.output) return []
    const raw = stream.output.split(/\n\n+/).map(p => p.trim()).filter(Boolean)
    return raw.map((p, i) => (editedParagraphs[i] !== undefined ? editedParagraphs[i] : p))
  }, [stream.output, editedParagraphs])

  function getFullDescription() {
    return paragraphs.join("\n\n")
  }

  function generate() {
    setEditedParagraphs({})
    setMetaTitle("")
    setMetaDesc("")
    setSeoError(null)
    stream.start(
      `${API_BASE_URL}/api/descriptions/generate`,
      idToken,
      {
        studio,
        is_compilation: isCompilation,
        performers,
        sex_positions: positions,
        categories: selectedCats.join(", "),
        target_keywords: keywords,
        wardrobe,
        model_properties: modelNotes || undefined,
      }
    )
  }

  async function generateSeo() {
    const desc = getFullDescription()
    if (!desc) return
    setSeoLoading(true)
    setSeoError(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/descriptions/seo`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({ description: desc, studio, performers }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setMetaTitle(data.meta_title ?? "")
      setMetaDesc(data.meta_description ?? "")
    } catch (e) {
      setSeoError(e instanceof Error ? e.message : "SEO generation failed")
    } finally {
      setSeoLoading(false)
    }
  }

  async function save() {
    if (!getFullDescription() || !selectedSceneId) return
    setSaving(true)
    setSaveMsg(null)
    try {
      await client.descriptions.save({
        scene_id: selectedSceneId,
        description: getFullDescription(),
        meta_title: metaTitle || undefined,
        meta_description: metaDesc || undefined,
      })
      setSaveMsg("Saved.")
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save"))
    } finally {
      setSaving(false)
    }
  }

  async function downloadDocx() {
    const desc = getFullDescription()
    if (!desc) return
    setDocxLoading(true)
    setDocxError(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/descriptions/docx`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          description: desc,
          meta_title: metaTitle || undefined,
          meta_description: metaDesc || undefined,
        }),
      })
      if (!res.ok) {
        // Server may return JSON error body alongside 4xx/5xx — surface it
        // so users see "generation failed: …" instead of a mysterious blank.
        let detail = `Server ${res.status}`
        try {
          const ct = res.headers.get("content-type") || ""
          if (ct.includes("json")) {
            const j = await res.json()
            if (j?.detail) detail += `: ${j.detail}`
          }
        } catch { /* leave default detail */ }
        throw new Error(detail)
      }
      const blob = await res.blob()
      if (blob.size === 0) {
        throw new Error("Server returned an empty file")
      }
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "description.docx"
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setDocxError(formatApiError(e, "Download"))
    } finally {
      setDocxLoading(false)
    }
  }

  const studioColor = STUDIO_COLOR[studio]

  return (
    <div>
      <PageHeader
        title="Descriptions"
        eyebrow={isCompilation ? "Compilation write-up" : "Scene write-up"}
        studioAccent={studio}
      />
      <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
        {/* ── Left — inputs ── */}
        <div style={{ width: 300, flexShrink: 0 }}>

        {/* Missing descriptions queue */}
        {missingDescScenes.length > 0 && (
          <div className="mb-4">
            <button
              onClick={() => setShowQueue(v => !v)}
              className="flex items-center justify-between w-full mb-2"
              style={{ fontSize: 11, color: "var(--color-text-muted)", fontWeight: 600 }}
            >
              <span>Missing Descriptions ({missingDescScenes.length})</span>
              <span style={{ fontSize: 10 }}>{showQueue ? "▾" : "▸"}</span>
            </button>
            {showQueue && (
              <div
                className="rounded overflow-y-auto"
                style={{
                  border: "1px solid var(--color-border)",
                  maxHeight: 200,
                }}
              >
                {missingDescScenes.slice(0, 30).map((s, i) => {
                  const readiness = (s.title ? 1 : 0) + (s.performers ? 1 : 0) + (s.plot ? 1 : 0) + (s.categories ? 1 : 0)
                  const dot = readiness >= 3 ? "var(--color-ok)" : readiness >= 1 ? "var(--color-warn)" : "var(--color-err)"
                  return (
                    <button
                      key={s.id}
                      onClick={() => autoPopulateFromScene(s)}
                      className="w-full text-left px-2.5 py-1.5 transition-colors hover:bg-[--color-elevated]"
                      style={{
                        borderBottom: i < missingDescScenes.length - 1 ? "1px solid var(--color-border-subtle, var(--color-border))" : undefined,
                        background: selectedSceneId === s.id ? "var(--color-elevated)" : undefined,
                      }}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="rounded-full shrink-0" style={{ width: 5, height: 5, background: dot }} />
                        <span className="font-mono" style={{ fontSize: 10, color: studioColor }}>{s.id}</span>
                        <span className="truncate" style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{s.performers || "—"}</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-col gap-3">

          {/* Studio */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio</label>
            <StudioSelector
              value={studio}
              onChange={(s) => {
                setStudio(s)
                setSelectedCats([])
                // Changing studio invalidates any selected scene + paragraph
                // edits from the previous studio; leaving them in state lets
                // a user save edits against the wrong studio's scene.
                setSelectedSceneId("")
                setEditedParagraphs({})
                setMetaTitle("")
                setMetaDesc("")
              }}
            />
          </div>

          {/* Is compilation */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsCompilation(v => !v)}
              className="px-2.5 py-1 rounded text-xs transition-colors"
              style={{
                background: isCompilation ? "color-mix(in srgb, var(--color-lime) 15%, transparent)" : "transparent",
                color: isCompilation ? "var(--color-lime)" : "var(--color-text-muted)",
                border: `1px solid ${isCompilation ? "color-mix(in srgb, var(--color-lime) 30%, transparent)" : "var(--color-border)"}`,
              }}
            >
              Compilation
            </button>
            <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
              {isCompilation ? "Compilation desc" : "Single scene"}
            </span>
          </div>

          {/* Performers */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Performers</label>
            <input
              type="text"
              value={performers}
              onChange={e => setPerformers(e.target.value)}
              placeholder="e.g. Lilly Bell, Seth Gamble"
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
            <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 3 }}>Comma-separated stage names — must match the scene's cast exactly</p>
          </div>

          {/* Positions */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Sex positions</label>
            <textarea
              value={positions}
              onChange={e => setPositions(e.target.value)}
              rows={3}
              placeholder="e.g. missionary, cowgirl, doggy…"
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>

          {/* Categories — grouped chips */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              Categories
              {selectedCats.length > 0 && (
                <button
                  onClick={() => setSelectedCats([])}
                  style={{ marginLeft: 6, color: "var(--color-text-faint)", fontSize: 10 }}
                >
                  clear
                </button>
              )}
            </label>
            <div className="grid grid-cols-2 gap-2">
              {(STUDIO_CATEGORY_GROUPS[studio] ?? []).map(({ label, cats }) => (
                <div key={label}>
                  <p style={{ fontSize: 9, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.07em", fontWeight: 600, marginBottom: 3 }}>
                    {label}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {cats.map(cat => {
                      const active = selectedCats.includes(cat)
                      return (
                        <button
                          key={cat}
                          onClick={() => toggleCat(cat)}
                          className="px-2 py-0.5 rounded text-xs transition-colors"
                          style={{
                            background: active ? `color-mix(in srgb, ${studioColor} 15%, transparent)` : "transparent",
                            color: active ? studioColor : "var(--color-text-faint)",
                            border: `1px solid ${active ? `color-mix(in srgb, ${studioColor} 30%, transparent)` : "var(--color-border)"}`,
                          }}
                        >
                          {cat}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Keywords */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Target keywords</label>
            <input
              type="text"
              value={keywords}
              onChange={e => setKeywords(e.target.value)}
              placeholder="e.g. VR porn, creampie VR"
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>

          {/* Wardrobe */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Wardrobe</label>
            <input
              type="text"
              value={wardrobe}
              onChange={e => setWardrobe(e.target.value)}
              placeholder="e.g. lingerie, jeans and crop top"
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>

          {/* Model notes */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              Model notes <span style={{ color: "var(--color-text-faint)" }}>(optional)</span>
            </label>
            <textarea
              value={modelNotes}
              onChange={e => setModelNotes(e.target.value)}
              rows={2}
              placeholder="Any special context about the talent…"
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>
        </div>

        {/* Generate */}
        <button
          onClick={generate}
          disabled={stream.streaming || !performers}
          className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
          style={{
            background: stream.streaming ? "var(--color-elevated)" : "var(--color-lime)",
            color: stream.streaming ? "var(--color-text-muted)" : "#0d0d0d",
            cursor: stream.streaming ? "wait" : "pointer",
            opacity: (!performers && !stream.streaming) ? 0.5 : 1,
          }}
        >
          {stream.streaming ? "Generating…" : !performers ? "Add performers to continue" : "Generate Description"}
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

      {/* ── Right — output ── */}
      <div style={{ flex: 1, minWidth: 0 }}>
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
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", fontSize: 13 }}>Queue is empty</span>
            <span>Select a scene from the left panel — fill the form and Generate.</span>
          </div>
        )}

        {(stream.output || stream.streaming) && (
          <>
            {/* Editor metadata strip: words · paragraphs · estimated read */}
            {stream.output && (() => {
              const words = stream.output.split(/\s+/).filter(Boolean).length
              const paraCount = paragraphs.length
              // ~200 WPM is typical silent reading speed for marketing copy;
              // matches the estimate used in the Streamlit descriptions view.
              const mins = Math.max(1, Math.round(words / 200))
              return (
                <div className="flex items-center gap-3 mb-2" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                  <span className="tabular-nums">{words.toLocaleString()} words</span>
                  {paraCount > 0 && !stream.streaming && (
                    <>
                      <span aria-hidden style={{ opacity: 0.5 }}>·</span>
                      <span className="tabular-nums">{paraCount} paragraph{paraCount === 1 ? "" : "s"}</span>
                    </>
                  )}
                  <span aria-hidden style={{ opacity: 0.5 }}>·</span>
                  <span className="tabular-nums">~{mins} min read</span>
                  {stream.streaming && (
                    <span style={{ opacity: 0.5, marginLeft: 4 }}>generating...</span>
                  )}
                </div>
              )
            })()}
            {/* Description body */}
            <div
              className="rounded mb-4 px-4 py-3"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
              }}
            >
              {stream.streaming ? (
                /* While streaming — show plain text with cursor */
                <p style={{ fontSize: 13, color: "var(--color-text)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                  {stream.output}
                  <span
                    style={{
                      display: "inline-block",
                      width: 6, height: 13,
                      background: studioColor,
                      marginLeft: 2,
                      verticalAlign: "middle",
                      animation: "streamCursorPulse 1s ease-in-out infinite",
                    }}
                  />
                </p>
              ) : (
                /* After streaming — editable paragraphs */
                <>
                  <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 8 }}>
                    Click any paragraph to edit
                  </p>
                  {paragraphs.map((para, i) => (
                    <EditableParagraph
                      key={i}
                      text={para}
                      index={i}
                      studioColor={studioColor}
                      onSave={(idx, newText) =>
                        setEditedParagraphs(prev => ({ ...prev, [idx]: newText }))
                      }
                    />
                  ))}
                </>
              )}
            </div>

            {/* SEO section */}
            {!stream.streaming && stream.output && (
              <div
                className="rounded mb-4 px-4 py-3"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", fontWeight: 600 }}>SEO Tags</span>
                  <button
                    onClick={generateSeo}
                    disabled={seoLoading}
                    className="px-2.5 py-1 rounded text-xs transition-colors"
                    style={{
                      background: "transparent",
                      color: seoLoading ? "var(--color-text-faint)" : studioColor,
                      border: `1px solid ${seoLoading ? "var(--color-border)" : `color-mix(in srgb, ${studioColor} 35%, transparent)`}`,
                      cursor: seoLoading ? "wait" : "pointer",
                    }}
                  >
                    {seoLoading ? "Generating…" : "Generate SEO Tags"}
                  </button>
                </div>
                {seoError && <p style={{ fontSize: 11, color: "var(--color-err)", marginBottom: 6 }}>{seoError}</p>}

                {/* Meta Title */}
                <div className="mb-2">
                  <label className="block mb-1" style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                    Meta Title <span style={{ opacity: 0.6 }}>({metaTitle.length}/60)</span>
                  </label>
                  <input
                    type="text"
                    value={metaTitle}
                    onChange={e => setMetaTitle(e.target.value.slice(0, 60))}
                    placeholder="Auto-generated on click above…"
                    maxLength={60}
                    className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                    style={{
                      background: "var(--color-elevated)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text)",
                    }}
                  />
                </div>

                {/* Meta Description */}
                <div>
                  <label className="block mb-1" style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                    Meta Description <span style={{ opacity: 0.6, color: metaDesc.length > 145 ? "var(--color-warn)" : undefined }}>({metaDesc.length}/155)</span>
                  </label>
                  <textarea
                    value={metaDesc}
                    onChange={e => setMetaDesc(e.target.value.slice(0, 155))}
                    rows={2}
                    placeholder="Auto-generated on click above…"
                    maxLength={155}
                    className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
                    style={{
                      background: "var(--color-elevated)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text)",
                    }}
                  />
                </div>
              </div>
            )}

            {/* Save / Download row */}
            {!stream.streaming && stream.output && (
              <div className="flex items-center gap-2 flex-wrap">
                <select
                  value={selectedSceneId}
                  onChange={e => setSelectedSceneId(e.target.value)}
                  className="px-2.5 py-1.5 rounded text-xs outline-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: selectedSceneId ? "var(--color-text)" : "var(--color-text-muted)",
                    minWidth: 220,
                  }}
                >
                  <option value="">— Select scene to save to —</option>
                  {studioScenes.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.id} — {s.title || "Untitled"}
                    </option>
                  ))}
                </select>

                <button
                  onClick={save}
                  disabled={saving || !selectedSceneId}
                  className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                  style={{
                    background: "var(--color-lime)",
                    color: "#0d0d0d",
                    opacity: (saving || !selectedSceneId) ? 0.5 : 1,
                  }}
                >
                  {saving ? "Saving…" : "Save"}
                </button>

                {isAdmin && (
                  <button
                    onClick={saveToGrail}
                    disabled={grailSaving || !selectedSceneId}
                    className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                    style={{
                      background: "color-mix(in srgb, var(--color-lime) 15%, transparent)",
                      color: "var(--color-lime)",
                      border: "1px solid color-mix(in srgb, var(--color-lime) 30%, transparent)",
                      opacity: (grailSaving || !selectedSceneId) ? 0.5 : 1,
                    }}
                  >
                    {grailSaving ? "Saving…" : "Save to Grail"}
                  </button>
                )}

                <button
                  onClick={downloadDocx}
                  disabled={docxLoading}
                  className="px-3 py-1.5 rounded text-xs transition-colors"
                  style={{
                    background: "transparent",
                    color: docxLoading ? "var(--color-text-faint)" : "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  {docxLoading ? "…" : "Download DOCX"}
                </button>

                {docxError && (
                  <span style={{ fontSize: 11, color: "var(--color-err)" }}>
                    DOCX failed: {docxError}
                  </span>
                )}
                {saveMsg && (
                  <span style={{
                    fontSize: 11,
                    color: /^Saved\b/.test(saveMsg) ? "var(--color-ok)" : "var(--color-err)",
                  }}>
                    {saveMsg}
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
    </div>
  )
}
