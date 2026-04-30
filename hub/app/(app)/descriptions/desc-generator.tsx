"use client"

import { useState, useMemo, useRef, useEffect } from "react"
import { Wand2 } from "lucide-react"
import { useStream } from "@/lib/sse"
import { api, API_BASE_URL, type Scene } from "@/lib/api"
import { revalidateAfterWrite } from "@/lib/cache-actions"
import { TAG_SCENES } from "@/lib/cache-tags"
import { formatApiError } from "@/lib/errors"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { StudioSelector } from "@/components/ui/studio-selector"
import { CopyButton } from "@/components/ui/copy-button"
import { WritingEmptyState } from "@/components/ui/writing-empty"
import { WritingHero } from "@/components/ui/writing-output"
import { PageHeader } from "@/components/ui/page-header"
import { studioAbbr } from "@/lib/studio-colors"
import { ApprovedTagsReference } from "@/components/ui/approved-tags-reference"
import { SeoModal } from "@/components/ui/seo-modal"
import { EditableParagraph } from "./editable-paragraph"

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
  const [plot, setPlot] = useState("")
  const [sceneType, setSceneType] = useState("")
  const [scriptLoading, setScriptLoading] = useState(false)

  // Inline-edited paragraphs (index → edited text)
  const [editedParagraphs, setEditedParagraphs] = useState<Record<number, string>>({})

  // SEO state
  const [metaTitle, setMetaTitle] = useState("")
  const [metaDesc, setMetaDesc] = useState("")
  const [seoLoading, setSeoLoading] = useState(false)
  const [seoError, setSeoError] = useState<string | null>(null)

  // Scene picker for saving
  const [selectedSceneId, setSelectedSceneId] = useState("")

  // Inline scene-title generator — wired to the selected scene so editors
  // can rename a scene without leaving the Descriptions view.
  const [genTitle, setGenTitle] = useState("")
  const [genTitleLoading, setGenTitleLoading] = useState(false)
  const [genTitleErr, setGenTitleErr] = useState<string | null>(null)
  const [genTitleSaving, setGenTitleSaving] = useState(false)

  const stream = useStream()
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<Date | null>(null)
  const [docxLoading, setDocxLoading] = useState(false)
  const [docxError, setDocxError] = useState<string | null>(null)
  const [seoOpen, setSeoOpen] = useState(false)

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

  // Scenes missing descriptions, sorted newest-first (by scene id). We show
  // the latest 10 by default — editors almost always want to write the
  // newest scene. For older ones they use the search box below (grail id or
  // performer), which lifts the cap.
  const missingAllDesc = useMemo(
    () => studioScenes
      .filter(s => !s.has_description)
      .sort((a, b) => b.id.localeCompare(a.id)),
    [studioScenes],
  )

  const [queueSearch, setQueueSearch] = useState("")
  const missingDescScenes = useMemo(() => {
    if (!queueSearch.trim()) return missingAllDesc.slice(0, 10)
    const q = queueSearch.trim().toLowerCase()
    return missingAllDesc.filter(
      s => s.id.toLowerCase().includes(q) || (s.performers ?? "").toLowerCase().includes(q),
    )
  }, [missingAllDesc, queueSearch])

  const [showQueue, setShowQueue] = useState(true)
  const [grailSaving, setGrailSaving] = useState(false)
  const [megaSaving, setMegaSaving] = useState(false)

  async function autoPopulateFromScene(scene: Scene) {
    setSelectedSceneId(scene.id)
    if (scene.performers) setPerformers(scene.performers)
    if (scene.categories) {
      const cats = scene.categories.split(",").map(c => c.trim()).filter(Boolean)
      setSelectedCats(cats.filter(c => availableCategories.includes(c)))
    }
    if (scene.tags) setKeywords(scene.tags)
    if (scene.title && !metaTitle) setMetaTitle(scene.title)
    // Reset script fields before fetch
    setPlot("")
    setSceneType("")
    setScriptLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/scenes/${scene.id}/script`, {
        headers: idToken ? { Authorization: `Bearer ${idToken}` } : {},
      })
      if (res.ok) {
        const data = await res.json()
        if (data.plot)       setPlot(data.plot)
        if (data.theme)      setModelNotes(data.theme)
        if (data.wardrobe_f) setWardrobe(data.wardrobe_f)
        if (data.scene_type) setSceneType(data.scene_type)
      }
    } catch { /* leave fields empty */ }
    finally { setScriptLoading(false) }
  }

  const selectedScene = useMemo(
    () => scenes.find(s => s.id === selectedSceneId) ?? null,
    [scenes, selectedSceneId],
  )

  async function generateSceneTitle() {
    if (!selectedScene) return
    setGenTitleLoading(true)
    setGenTitleErr(null)
    try {
      const { title } = await client.scenes.generateTitle(selectedScene.id, {
        female: selectedScene.female,
        male: selectedScene.male,
        theme: selectedScene.theme,
        plot: selectedScene.plot,
        // Editor-in-progress wardrobe wins over any stale scene row value
        wardrobe_f: wardrobe || undefined,
      })
      setGenTitle(title)
    } catch (e) {
      setGenTitleErr(formatApiError(e, "Title"))
    } finally {
      setGenTitleLoading(false)
    }
  }

  async function applySceneTitle() {
    if (!genTitle || !selectedScene) return
    setGenTitleSaving(true)
    setGenTitleErr(null)
    try {
      await client.scenes.updateTitle(selectedScene.id, genTitle)
      void revalidateAfterWrite([TAG_SCENES])
      setGenTitle("")
      setSaveMsg("Title saved.")
      setTimeout(() => setSaveMsg(null), 1500)
    } catch (e) {
      setGenTitleErr(formatApiError(e, "Save"))
    } finally {
      setGenTitleSaving(false)
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

  async function saveToMega() {
    if (!getFullDescription() || !selectedSceneId) return
    setMegaSaving(true)
    setSaveMsg(null)
    try {
      const res = await client.descriptions.saveMega({
        scene_id: selectedSceneId,
        description: getFullDescription(),
        title: selectedScene?.title || undefined,
        meta_title: metaTitle || undefined,
        meta_description: metaDesc || undefined,
      })
      setSaveMsg(`Saved to MEGA.`)
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save to MEGA"))
    } finally {
      setMegaSaving(false)
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
    setSavedAt(null)
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
        plot: plot || undefined,
        scene_type: sceneType || undefined,
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
      setSavedAt(new Date())
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

  // V2 header stats — shown in eyebrow and subtitle.
  const missingCount = missingAllDesc.length
  const totalStudio = studioScenes.length
  const outputWords = stream.output
    ? stream.output.split(/\s+/).filter(Boolean).length
    : 0
  const subtitle = selectedScene
    ? `${selectedScene.id} · ${selectedScene.performers || "—"}${selectedScene.title ? ` · ${selectedScene.title}` : ""}`
    : `${missingCount} missing of ${totalStudio} ${studioAbbr(studio)} scenes`

  return (
    <div>
      <PageHeader
        title="Descriptions"
        eyebrow={`WRITING ROOM · ${isCompilation ? "COMPILATION" : "SCENE"} · ${studioAbbr(studio)}`}
        subtitle={subtitle}
        studioAccent={studio}
        actions={
          <button
            onClick={() => setIsCompilation(v => !v)}
            role="switch"
            aria-checked={isCompilation}
            style={{
              padding: "5px 11px",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              background: isCompilation
                ? "color-mix(in srgb, var(--color-lime) 14%, transparent)"
                : "transparent",
              color: isCompilation ? "var(--color-lime)" : "var(--color-text-muted)",
              border: `1px solid ${isCompilation
                ? "color-mix(in srgb, var(--color-lime) 32%, transparent)"
                : "var(--color-border)"}`,
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            Compilation
          </button>
        }
      />
      <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
        {/* ── Left — inputs ── */}
        <div style={{ width: 300, flexShrink: 0 }}>

        {/* Missing descriptions queue — latest 10 by default; search to expand. */}
        {missingAllDesc.length > 0 && (
          <div className="mb-4">
            <button
              onClick={() => setShowQueue(v => !v)}
              className="flex items-center justify-between w-full mb-2"
              style={{ fontSize: 11, color: "var(--color-text-muted)", fontWeight: 600 }}
            >
              <span>
                Missing Descriptions
                <span style={{ color: "var(--color-text-faint)", fontWeight: 400, marginLeft: 4 }}>
                  {queueSearch.trim()
                    ? `${missingDescScenes.length} match${missingDescScenes.length === 1 ? "" : "es"}`
                    : `latest ${Math.min(10, missingAllDesc.length)} of ${missingAllDesc.length}`}
                </span>
              </span>
              <span style={{ fontSize: 10 }}>{showQueue ? "▾" : "▸"}</span>
            </button>
            {showQueue && (
              <>
                <input
                  type="search"
                  value={queueSearch}
                  onChange={e => setQueueSearch(e.target.value)}
                  placeholder="Search by scene id or performer…"
                  className="w-full px-2.5 py-1.5 rounded mb-1.5 outline-none"
                  style={{
                    fontSize: 11,
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <div
                  className="rounded overflow-y-auto"
                  style={{
                    border: "1px solid var(--color-border)",
                    maxHeight: 200,
                  }}
                >
                  {missingDescScenes.length === 0 && queueSearch.trim() && (
                    <div style={{ padding: "10px 12px", fontSize: 11, color: "var(--color-text-faint)", textAlign: "center" }}>
                      No matches — try a scene id (e.g. VRA0523) or a performer.
                    </div>
                  )}
                  {missingDescScenes.map((s, i) => {
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
              </>
            )}
          </div>
        )}

        <div className="flex flex-col gap-3">

          {/* Selected scene — title generator */}
          {selectedScene && (
            <div
              className="rounded px-2.5 py-2"
              style={{
                background: "var(--color-surface)",
                border: `1px solid color-mix(in srgb, ${studioColor} 25%, var(--color-border))`,
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono" style={{ fontSize: 10, color: studioColor }}>
                  {selectedScene.id}
                </span>
                <button
                  onClick={generateSceneTitle}
                  disabled={genTitleLoading}
                  className="flex items-center gap-1 px-2 py-0.5 rounded transition-colors"
                  style={{
                    fontSize: 10,
                    background: "transparent",
                    color: genTitleLoading ? "var(--color-text-faint)" : studioColor,
                    border: `1px solid ${genTitleLoading ? "var(--color-border)" : `color-mix(in srgb, ${studioColor} 35%, transparent)`}`,
                    cursor: genTitleLoading ? "wait" : "pointer",
                  }}
                  title="Generate a title from the scene's script"
                >
                  <Wand2 size={10} aria-hidden="true" />
                  {genTitleLoading ? "…" : "Title"}
                </button>
              </div>
              <p style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.35 }}>
                {selectedScene.title || <span style={{ color: "var(--color-text-faint)" }}>Untitled</span>}
              </p>
              {genTitleErr && (
                <p style={{ fontSize: 10, color: "var(--color-err)", marginTop: 4 }}>{genTitleErr}</p>
              )}
              {genTitle && (
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className="flex-1 truncate"
                    style={{
                      fontSize: 11,
                      color: "var(--color-text)",
                      fontWeight: 600,
                    }}
                    title={genTitle}
                  >
                    {genTitle}
                  </span>
                  <button
                    onClick={applySceneTitle}
                    disabled={genTitleSaving}
                    className="px-2 py-0.5 rounded"
                    style={{
                      fontSize: 10,
                      background: genTitleSaving ? "var(--color-elevated)" : "var(--color-lime)",
                      color: genTitleSaving ? "var(--color-text-muted)" : "var(--color-lime-ink)",
                      fontWeight: 600,
                      cursor: genTitleSaving ? "wait" : "pointer",
                    }}
                  >
                    {genTitleSaving ? "…" : "Apply"}
                  </button>
                  <button
                    onClick={() => setGenTitle("")}
                    className="px-1.5 py-0.5 rounded"
                    style={{
                      fontSize: 10,
                      color: "var(--color-text-faint)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Studio */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio</label>
            <StudioSelector
              value={studio}
              onChange={(s) => {
                if (s === studio) return
                // Changing studio invalidates any selected scene + paragraph
                // edits from the previous studio; leaving them in state lets
                // a user save edits against the wrong studio's scene. Warn
                // before destroying work the user can see on screen.
                const hasDirtyDraft =
                  !!selectedSceneId ||
                  Object.keys(editedParagraphs).length > 0 ||
                  metaTitle !== "" ||
                  metaDesc !== ""
                if (hasDirtyDraft) {
                  const ok = window.confirm(
                    `Switching from ${studioAbbr(studio)} to ${studioAbbr(s)} will clear the selected scene, paragraph edits, and SEO metadata for ${studioAbbr(studio)}. Continue?`,
                  )
                  if (!ok) return
                }
                setStudio(s)
                setSelectedCats([])
                setSelectedSceneId("")
                setEditedParagraphs({})
                setMetaTitle("")
                setMetaDesc("")
              }}
            />
          </div>

          {/* Compilation toggle lives in the PageHeader actions now. */}

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
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
              <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
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
            </div>
            <div style={{ marginBottom: 6 }}>
              <ApprovedTagsReference studio={studio} />
            </div>
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

          {/* Scene plot — populated automatically from Scripts Sheet via autoPopulateFromScene */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              Scene plot{" "}
              {scriptLoading && <span style={{ color: "var(--color-text-faint)" }}>fetching…</span>}
              {!scriptLoading && sceneType && (
                <span style={{ marginLeft: 6, color: "var(--color-text-faint)", fontFamily: "var(--font-mono, monospace)" }}>
                  {sceneType}
                </span>
              )}
            </label>
            <textarea
              value={plot}
              onChange={e => setPlot(e.target.value)}
              rows={4}
              placeholder="Auto-filled from Scripts Sheet when you pick a scene. Paste manually if needed."
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>
        </div>

        {/* Generate — lime fill reserved for the armed state; inert state
            uses outlined-faint so users can tell a click will do nothing. */}
        {(() => {
          const inert = !performers && !stream.streaming
          return (
            <button
              onClick={generate}
              disabled={stream.streaming || !performers}
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
              {stream.streaming ? "Generating…" : inert ? "Add performers to continue" : "Generate Description"}
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

      {/* ── Right — output (V2 ec-block frame) ── */}
      <div style={{ flex: 1, minWidth: 0 }}>
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
              {isCompilation ? "Compilation" : "Description"}
            </h2>
            <div
              className="act"
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--color-text-muted)",
              }}
            >
              {outputWords > 0 && (
                <span className="tabular-nums">{outputWords.toLocaleString()} words</span>
              )}
              {savedAt && (
                <span style={{ color: "var(--color-ok)" }}>
                  Saved {savedAt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
                </span>
              )}
              {stream.streaming && <span style={{ color: "var(--color-lime)" }}>Streaming</span>}
              {!stream.streaming && stream.output && (
                <CopyButton text={getFullDescription()} label="Copy" />
              )}
            </div>
          </header>

          <div style={{ padding: "14px 16px" }}>
        {stream.error && <ErrorAlert className="mb-3">{stream.error}</ErrorAlert>}

        {!stream.output && !stream.streaming && (
          <WritingEmptyState
            icon="≡"
            primary="Select a scene, configure the form, and generate — the description flows here like an article being written."
            helper="Pick a row from the Missing queue on the left."
          />
        )}

        {(stream.output || stream.streaming) && (
          <>
            {/* Paragraph count + read time — words now live in the ec-block header. */}
            {stream.output && !stream.streaming && paragraphs.length > 0 && (() => {
              const words = stream.output.split(/\s+/).filter(Boolean).length
              const mins = Math.max(1, Math.round(words / 200))
              return (
                <div className="flex items-center gap-3 mb-2" style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                  <span className="tabular-nums">{paragraphs.length} paragraph{paragraphs.length === 1 ? "" : "s"}</span>
                  <span aria-hidden style={{ opacity: 0.5 }}>·</span>
                  <span className="tabular-nums">~{mins} min read</span>
                </div>
              )
            })()}
            {/* Description body — paper writing surface (Writing Room v3).
                Newsreader serif body face for long-form reading. */}
            <div
              className="writing-paper rounded mb-4"
              style={{ padding: "32px 36px" }}
            >
              <WritingHero
                studioAbbr={studioAbbr(studio)}
                studioColor={studioColor}
                meta={selectedScene?.id ?? null}
                title={selectedScene?.title || performers || "Untitled"}
                byline={performers ? `by ${performers}` : null}
              />
              {stream.streaming ? (
                /* While streaming — show serif body with pulsing cursor */
                <p className="writing-body" style={{ whiteSpace: "pre-wrap" }}>
                  {stream.output}
                  <span
                    style={{
                      display: "inline-block",
                      width: 2, height: "1em",
                      background: studioColor,
                      marginLeft: 3,
                      verticalAlign: "text-bottom",
                      animation: "streamCursorPulse 1s ease-in-out infinite",
                      borderRadius: 1,
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
                      onRegenerate={async (idx, feedbackText) => {
                        const res = await client.descriptions.regenerateParagraph({
                          studio,
                          paragraph: para,
                          paragraph_index: idx,
                          performer: performers || selectedScene?.female || "",
                          title: selectedScene?.title ?? "",
                          plot: selectedScene?.theme ?? "",
                          feedback: feedbackText,
                        })
                        const next = res.paragraph?.trim() ?? ""
                        if (next) {
                          setEditedParagraphs(prev => ({ ...prev, [idx]: next }))
                          return next
                        }
                        return null
                      }}
                    />
                  ))}
                </>
              )}
            </div>

            {/* SEO summary chip — opens the full editor in a modal. */}
            {!stream.streaming && stream.output && (
              <button
                type="button"
                onClick={() => setSeoOpen(true)}
                className="mb-4"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)" }}>
                    SEO Tags
                  </span>
                  <span style={{ fontSize: 12, color: "var(--color-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {metaTitle || metaDesc ? (
                      <>
                        {metaTitle || <span style={{ color: "var(--color-text-faint)" }}>No title</span>}
                        {metaDesc && <span style={{ color: "var(--color-text-muted)" }}> · {metaDesc.slice(0, 80)}{metaDesc.length > 80 ? "…" : ""}</span>}
                      </>
                    ) : (
                      <span style={{ color: "var(--color-text-faint)" }}>Not generated yet — click to open editor</span>
                    )}
                  </span>
                </div>
                <span
                  style={{
                    flexShrink: 0,
                    padding: "3px 9px",
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: studioColor,
                    border: `1px solid color-mix(in srgb, ${studioColor} 32%, transparent)`,
                  }}
                >
                  {metaTitle || metaDesc ? "Edit" : "Open"} →
                </span>
              </button>
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

                {(() => {
                  const inert = !selectedSceneId && !saving
                  return (
                    <button
                      onClick={save}
                      disabled={saving || !selectedSceneId}
                      className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                      title={inert ? "Pick a scene from the dropdown to enable saving" : undefined}
                      style={{
                        background: saving ? "var(--color-elevated)" : inert ? "transparent" : "var(--color-lime)",
                        color: saving ? "var(--color-text-muted)" : inert ? "var(--color-text-faint)" : "var(--color-lime-ink)",
                        border: inert ? "1px solid var(--color-border)" : "1px solid transparent",
                        cursor: saving ? "wait" : inert ? "not-allowed" : "pointer",
                      }}
                    >
                      {saving ? "Saving…" : "Save"}
                    </button>
                  )
                })()}

                {(() => {
                  const inert = !selectedSceneId && !megaSaving
                  return (
                    <button
                      onClick={saveToMega}
                      disabled={megaSaving || !selectedSceneId}
                      className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                      title={inert ? "Pick a scene from the dropdown to save" : undefined}
                      style={{
                        background: megaSaving ? "var(--color-elevated)" : inert ? "transparent" : "var(--color-lime)",
                        color: megaSaving ? "var(--color-text-muted)" : inert ? "var(--color-text-faint)" : "var(--color-lime-ink)",
                        border: inert ? "1px solid var(--color-border)" : "1px solid transparent",
                        cursor: megaSaving ? "wait" : inert ? "not-allowed" : "pointer",
                      }}
                    >
                      {megaSaving ? "Saving…" : "Save to MEGA"}
                    </button>
                  )
                })()}

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
        </section>
      </div>
    </div>

    {seoOpen && (
      <SeoModal
        metaTitle={metaTitle}
        metaDesc={metaDesc}
        studioColor={studioColor}
        loading={seoLoading}
        error={seoError}
        onChangeTitle={setMetaTitle}
        onChangeDesc={setMetaDesc}
        onGenerate={generateSeo}
        onClose={() => setSeoOpen(false)}
      />
    )}
    </div>
  )
}
