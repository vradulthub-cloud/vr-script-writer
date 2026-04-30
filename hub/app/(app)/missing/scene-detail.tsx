"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { createPortal } from "react-dom"
import { X, Wand2, FolderPlus, ImageOff, Maximize2 } from "lucide-react"
import { api, thumbnailUrl, storyboardImageUrl, type Scene, type NamingIssue } from "@/lib/api"
import { revalidateAfterWrite } from "@/lib/cache-actions"
import { TAG_SCENES } from "@/lib/cache-tags"
import { completionPct } from "@/lib/scene-utils"
import { formatApiError } from "@/lib/errors"
import { useIdToken } from "@/hooks/use-id-token"
import { StudioBadge } from "@/components/ui/studio-badge"
import { studioColor } from "@/lib/studio-colors"

const ASSET_COLS = [
  { key: "has_description" as const, label: "Description" },
  { key: "has_videos" as const,      label: "Videos" },
  { key: "has_thumbnail" as const,   label: "Thumbnail" },
  { key: "has_photos" as const,      label: "Photos" },
  { key: "has_storyboard" as const,  label: "Storyboard" },
]

interface SceneDetailProps {
  scene: Scene
  idToken: string | undefined
  onClose: () => void
  onSceneUpdate: (updated: Scene) => void
}

/**
 * Side-panel scene detail. Renders inside a ~480px right-rail frame that the
 * grid makes room for via flex layout (see scene-grid.tsx). Keeps the grid
 * visible so editors can triage multiple scenes without full-page navigation.
 *
 * Dirty-state signal: each inline editable field tracks whether its local
 * value diverges from the server snapshot. A muted "Unsaved" pill appears
 * inline and `beforeunload` blocks navigation when any field is dirty.
 */
export function SceneDetail({ scene: initialScene, idToken: serverToken, onClose, onSceneUpdate }: SceneDetailProps) {
  const idToken = useIdToken(serverToken)
  const client = api(idToken ?? null)
  const color = studioColor(initialScene.studio)

  const [scene, setScene] = useState(initialScene)
  // Reset local state when the parent swaps scenes. We intentionally key this
  // effect on initialScene.id only: we want to reset when the user clicks a
  // *different* scene card, not when the parent patches fields on the current
  // scene (e.g. after onSceneUpdate → a title save comes back from the server).
  // The `initialScene` reference changes on every re-render; only its id is
  // the stable scene-swap signal.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setScene(initialScene)
    setEditingField(null)
    setEditValue("")
    setSaveMsg("")
    setGenTitle("")
    setFolderMsg("")
    setThumbFailed(false)
  }, [initialScene.id])

  // Editable fields
  const [editingField, setEditingField] = useState<"title" | "categories" | "tags" | null>(null)
  const [editValue, setEditValue] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState("")

  // Title generation
  const [genTitle, setGenTitle] = useState("")
  const [generating, setGenerating] = useState(false)

  // Naming validation
  const [namingIssues, setNamingIssues] = useState<NamingIssue[] | null>(null)
  const [namingOk, setNamingOk] = useState<boolean | null>(null)
  const [namingError, setNamingError] = useState<string | null>(null)

  // MEGA folder
  const [folderCreating, setFolderCreating] = useState(false)
  const [folderMsg, setFolderMsg] = useState("")

  // Thumbnail load state — server sync can claim has_thumbnail=true before
  // the MEGA proxy actually has the file
  const [thumbFailed, setThumbFailed] = useState(false)

  // Dirty state — any editing field with local != original
  const isDirty = editingField !== null && editValue !== (scene[editingField] ?? "")

  // Block accidental nav-away when dirty
  useEffect(() => {
    if (!isDirty) return
    function onBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", onBeforeUnload)
    return () => window.removeEventListener("beforeunload", onBeforeUnload)
  }, [isDirty])

  // Guard the close button: if dirty, confirm before discarding
  function requestClose() {
    if (isDirty && !confirm("You have unsaved changes. Discard them?")) return
    onClose()
  }

  // Close on ESC
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") requestClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [isDirty])

  // Load naming issues when scene changes
  const loadNamingIssues = useCallback(() => {
    setNamingIssues(null)
    setNamingOk(null)
    setNamingError(null)
    client.scenes.namingIssues(scene.id).then((data) => {
      setNamingIssues(data.issues)
      setNamingOk(data.ok)
    }).catch((e) => {
      console.warn("[scene-detail] Failed to load naming issues:", e)
      setNamingError(formatApiError(e, "Check naming"))
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene.id])

  useEffect(() => {
    loadNamingIssues()
  }, [loadNamingIssues])

  function startEdit(field: "title" | "categories" | "tags") {
    setEditingField(field)
    setEditValue(scene[field] ?? "")
    setSaveMsg("")
  }

  async function saveField() {
    if (!editingField) return
    setSaving(true)
    setSaveMsg("")
    try {
      if (editingField === "title") await client.scenes.updateTitle(scene.id, editValue)
      else if (editingField === "categories") await client.scenes.updateCategories(scene.id, editValue)
      else if (editingField === "tags") await client.scenes.updateTags(scene.id, editValue)
      void revalidateAfterWrite([TAG_SCENES])

      const updated = { ...scene, [editingField]: editValue }
      setScene(updated)
      onSceneUpdate(updated)
      setSaveMsg("Saved")
      setTimeout(() => { setEditingField(null); setSaveMsg("") }, 800)
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save"))
    } finally {
      setSaving(false)
    }
  }

  async function generateTitle() {
    setGenerating(true)
    try {
      const { title } = await client.scenes.generateTitle(scene.id, {
        female: scene.female,
        theme: scene.theme,
        plot: scene.plot,
      })
      setGenTitle(title)
    } catch {
      setGenTitle("")
      setSaveMsg("Title generation failed")
    } finally {
      setGenerating(false)
    }
  }

  async function applyGenTitle() {
    if (!genTitle) return
    setSaving(true)
    try {
      await client.scenes.updateTitle(scene.id, genTitle)
      void revalidateAfterWrite([TAG_SCENES])
      const updated = { ...scene, title: genTitle }
      setScene(updated)
      onSceneUpdate(updated)
      setGenTitle("")
      setSaveMsg("Title saved")
      setTimeout(() => setSaveMsg(""), 1200)
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save"))
    } finally {
      setSaving(false)
    }
  }

  async function createFolder() {
    setFolderCreating(true)
    setFolderMsg("")
    try {
      await client.scenes.createFolder(scene.id)
      setFolderMsg("Folder queued")
    } catch {
      setFolderMsg("Failed to queue")
    } finally {
      setFolderCreating(false)
    }
  }

  const pct = completionPct(scene)
  const pctColor = pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : "var(--color-err)"

  // View Transitions: name must match what scene-grid's SceneCard emits so
  // the browser morphs the card frame → panel header.
  const frameName = `scene-frame-${scene.id}`
  const codeName  = `scene-code-${scene.id}`

  return (
    <div
      role="complementary"
      aria-label={`Scene ${scene.id} details`}
      style={{
        display: "flex",
        flexDirection: "column",
        // Constrain to viewport minus the fixed topbar and the panel's sticky
        // top offset (12px) plus a small breathing gap at the bottom. The
        // rest flows through the inner scrollable body.
        maxHeight: "calc(100vh - var(--spacing-topbar) - 2 * var(--spacing-panel-gap))",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
        viewTransitionName: frameName,
        contain: "layout",
      }}
    >
      {/* ─── Header: thumb + identity + full-width progress ───────────────── */}
      <div
        style={{
          padding: "14px",
          borderBottom: "1px solid var(--color-border)",
          background: `color-mix(in srgb, ${color} 6%, var(--color-surface))`,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <SceneThumbnail
            sceneId={scene.id}
            hasThumbnail={scene.has_thumbnail}
            hasFolder={Boolean(scene.mega_path)}
            failed={thumbFailed}
            onError={() => setThumbFailed(true)}
            onRetry={() => setThumbFailed(false)}
          />

          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Row 1: identity only — stays on one line even at 13" laptop widths */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, minWidth: 0 }}>
              <span
                className="font-mono font-semibold"
                style={{ fontSize: 15, color, viewTransitionName: codeName, flexShrink: 0 }}
              >
                {scene.id}
              </span>
              <StudioBadge studio={scene.studio} />
              {isDirty && (
                <span
                  style={{
                    fontSize: 9, fontWeight: 600, letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    padding: "1px 6px", borderRadius: 3,
                    background: "color-mix(in srgb, var(--color-warn) 15%, transparent)",
                    color: "var(--color-warn)",
                    border: "1px solid color-mix(in srgb, var(--color-warn) 30%, transparent)",
                    flexShrink: 0,
                  }}
                >
                  Unsaved
                </span>
              )}
            </div>
            {/* Row 2: performers — own line, full width, ellipsis safe */}
            <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {scene.performers || "No performers listed"}
            </div>
            {/* Row 3: metadata (date + Comp pill) — demoted to caption-level */}
            {(scene.release_date || scene.is_compilation) && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                {scene.release_date && (
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
                    {scene.release_date}
                  </span>
                )}
                {scene.is_compilation && (
                  <span
                    className="rounded"
                    style={{
                      fontSize: 9,
                      fontWeight: 600,
                      letterSpacing: "0.05em",
                      textTransform: "uppercase",
                      padding: "1px 5px",
                      background: "color-mix(in srgb, var(--color-warn) 15%, transparent)",
                      color: "var(--color-warn)",
                    }}
                  >
                    Compilation
                  </span>
                )}
              </div>
            )}
          </div>

          <button
            onClick={requestClose}
            aria-label="Close panel"
            className="transition-colors"
            style={{
              color: "var(--color-text-muted)",
              background: "none",
              border: "none",
              padding: 4,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              borderRadius: 3,
              flexShrink: 0,
              marginTop: -2,
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Full-width progress bar + heavy % number */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
          <div
            className="rounded-full overflow-hidden"
            style={{ flex: 1, height: 3, background: "var(--color-border)" }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${pct}%`, background: pctColor }}
            />
          </div>
          <span
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: pctColor,
              fontVariantNumeric: "tabular-nums",
              flexShrink: 0,
              minWidth: 40,
              textAlign: "right",
            }}
          >
            {pct}%
          </span>
        </div>
      </div>

      {/* ─── Scrollable body ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "14px" }}>
        {/* Asset status tiles */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(68px, 1fr))", gap: 6, marginBottom: 18 }}>
          {ASSET_COLS.map((col) => {
            const present = scene[col.key]
            return (
              <div
                key={col.key}
                title={present ? `${col.label} present` : `${col.label} missing`}
                style={{
                  padding: "8px 6px",
                  borderRadius: 4,
                  background: "var(--color-base)",
                  border: `1px solid ${present ? "color-mix(in srgb, var(--color-ok) 30%, transparent)" : "var(--color-border)"}`,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 2,
                }}
              >
                <span style={{ fontSize: 14, color: present ? "var(--color-ok)" : "var(--color-err)", lineHeight: 1 }}>
                  {present ? "✓" : "✕"}
                </span>
                <span style={{ fontSize: 9, fontWeight: 500, color: "var(--color-text-muted)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
                  {col.label === "Description" ? "Desc" : col.label === "Storyboard" ? "Story" : col.label === "Thumbnail" ? "Thumb" : col.label}
                </span>
              </div>
            )
          })}
        </div>

        {/* ── Zone: Metadata ─────────────────────────────────────────── */}
        <SectionLabel>Metadata</SectionLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 18 }}>
          <EditableField
            label="Title"
            value={scene.title}
            editing={editingField === "title"}
            editValue={editValue}
            onEdit={() => startEdit("title")}
            onCancel={() => setEditingField(null)}
            onChange={setEditValue}
            onSave={saveField}
            saving={saving}
            saveMsg={editingField === "title" ? saveMsg : ""}
            extra={
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                <button
                  onClick={generateTitle}
                  disabled={generating}
                  className="flex items-center gap-1.5 rounded transition-colors"
                  style={{
                    padding: "3px 8px",
                    fontSize: 11,
                    background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                    color: "var(--color-lime)",
                    border: "1px solid color-mix(in srgb, var(--color-lime) 25%, transparent)",
                    opacity: generating ? 0.5 : 1,
                    cursor: generating ? "wait" : "pointer",
                  }}
                >
                  <Wand2 size={10} />
                  {generating ? "Generating…" : "Generate"}
                </button>
                {genTitle && (
                  <>
                    <span style={{ fontSize: 11, color: "var(--color-text)", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {genTitle}
                    </span>
                    <button
                      onClick={applyGenTitle}
                      className="rounded font-medium"
                      style={{ padding: "2px 8px", fontSize: 11, background: "var(--color-lime)", color: "#000" }}
                    >
                      Apply
                    </button>
                  </>
                )}
              </div>
            }
          />
          <EditableField
            label="Categories"
            value={scene.categories}
            editing={editingField === "categories"}
            editValue={editValue}
            onEdit={() => startEdit("categories")}
            onCancel={() => setEditingField(null)}
            onChange={setEditValue}
            onSave={saveField}
            saving={saving}
            saveMsg={editingField === "categories" ? saveMsg : ""}
            multiline
          />
          <EditableField
            label="Tags"
            value={scene.tags}
            editing={editingField === "tags"}
            editValue={editValue}
            onEdit={() => startEdit("tags")}
            onCancel={() => setEditingField(null)}
            onChange={setEditValue}
            onSave={saveField}
            saving={saving}
            saveMsg={editingField === "tags" ? saveMsg : ""}
            multiline
          />

          {scene.plot && (
            <div>
              <FieldLabel>Plot</FieldLabel>
              <div
                className="rounded"
                style={{
                  padding: "7px 10px",
                  fontSize: 11,
                  color: "var(--color-text-muted)",
                  background: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                  lineHeight: 1.5,
                }}
              >
                {scene.plot}
              </div>
            </div>
          )}
        </div>

        {/* ── Zone: Storyboard preview strip ─────────────────────────── */}
        {scene.has_storyboard && (
          <>
            <SectionLabel>Storyboard</SectionLabel>
            <div style={{ marginBottom: 18 }}>
              <StoryboardStrip sceneId={scene.id} idToken={idToken} />
            </div>
          </>
        )}

        {/* ── Zone: Naming & Folder ──────────────────────────────────── */}
        <SectionLabel>Naming &amp; Folder</SectionLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
          {namingError ? (
            <div
              className="rounded flex items-center justify-between gap-2"
              style={{
                padding: "7px 10px",
                fontSize: 11,
                color: "var(--color-err)",
                background: "color-mix(in srgb, var(--color-err) 8%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-err) 20%, transparent)",
              }}
            >
              <span>{namingError}</span>
              <button
                onClick={loadNamingIssues}
                className="px-2 py-0.5 rounded"
                style={{ fontSize: 11, color: "var(--color-text)", border: "1px solid var(--color-border)" }}
              >
                Retry
              </button>
            </div>
          ) : namingOk === null ? (
            <div style={{ fontSize: 11, color: "var(--color-text-faint)", padding: "6px 0" }}>
              Checking naming…
            </div>
          ) : namingOk ? (
            <div
              className="rounded"
              style={{
                padding: "7px 10px",
                fontSize: 11,
                color: "var(--color-ok)",
                background: "color-mix(in srgb, var(--color-ok) 8%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-ok) 20%, transparent)",
              }}
            >
              ✓ All naming conventions OK
            </div>
          ) : (
            <div
              className="rounded space-y-1"
              style={{
                padding: "7px 10px",
                background: "color-mix(in srgb, var(--color-err) 8%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-err) 20%, transparent)",
              }}
            >
              {namingIssues?.map((issue, i) => {
                const isNoFolder = issue.issue.toLowerCase().includes("no mega folder")
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--color-err)" }}>
                    <span className="font-mono" style={{ fontSize: 10, flex: 1 }}>
                      {issue.file} <span style={{ color: "color-mix(in srgb, var(--color-err) 70%, var(--color-text-muted))" }}>— {issue.issue}</span>
                    </span>
                    {isNoFolder && (
                      <button
                        onClick={createFolder}
                        disabled={folderCreating}
                        className="rounded"
                        style={{
                          padding: "1px 6px",
                          fontSize: 10,
                          fontWeight: 600,
                          background: "color-mix(in srgb, var(--color-err) 15%, transparent)",
                          color: "var(--color-err)",
                          border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
                          cursor: folderCreating ? "wait" : "pointer",
                          flexShrink: 0,
                        }}
                      >
                        {folderCreating ? "…" : "Create"}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Create Folder fallback when mega_path empty and not flagged above */}
          {!scene.mega_path && namingOk && (
            <button
              onClick={createFolder}
              disabled={folderCreating}
              className="flex items-center gap-1.5 rounded transition-colors"
              style={{
                padding: "5px 10px",
                fontSize: 11,
                background: "color-mix(in srgb, var(--color-warn) 10%, transparent)",
                color: "var(--color-warn)",
                border: "1px solid color-mix(in srgb, var(--color-warn) 30%, transparent)",
                opacity: folderCreating ? 0.5 : 1,
                alignSelf: "flex-start",
              }}
            >
              <FolderPlus size={11} />
              {folderCreating ? "Creating…" : "Create MEGA Folder"}
            </button>
          )}

          {folderMsg && (
            <span
              style={{
                fontSize: 10,
                color: folderMsg.includes("queued") ? "var(--color-ok)" : "var(--color-err)",
              }}
            >
              {folderMsg}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section label sub-components
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: "var(--color-text-faint)",
        marginBottom: 8,
        paddingBottom: 4,
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      {children}
    </div>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        color: "var(--color-text-faint)",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        marginBottom: 4,
      }}
    >
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scene thumbnail sub-component
// ---------------------------------------------------------------------------

const THUMB_WIDTH = 120

// ─── Storyboard preview strip ────────────────────────────────────────────────
// Compact horizontal row of every storyboard JPG for the scene. Click any
// frame to open it in the same lightbox the main thumbnail uses.

function StoryboardStrip({
  sceneId,
  idToken,
}: {
  sceneId: string
  idToken: string | undefined
}) {
  const [files, setFiles] = useState<Array<{ filename: string; size: number }> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openFile, setOpenFile] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api(idToken ?? null).scenes.storyboard(sceneId)
      .then(res => {
        if (!cancelled) setFiles(res.files)
      })
      .catch(e => {
        if (!cancelled) setError(formatApiError(e, "Load storyboard"))
      })
    return () => { cancelled = true }
  }, [sceneId, idToken])

  if (error) {
    return (
      <div style={{
        padding: "7px 10px", fontSize: 11, color: "var(--color-err)",
        background: "color-mix(in srgb, var(--color-err) 8%, transparent)",
        border: "1px solid color-mix(in srgb, var(--color-err) 20%, transparent)",
        borderRadius: 4,
      }}>
        {error}
      </div>
    )
  }

  if (files === null) {
    return (
      <div style={{ fontSize: 11, color: "var(--color-text-faint)" }}>Loading storyboard…</div>
    )
  }

  if (files.length === 0) {
    return (
      <div style={{ fontSize: 11, color: "var(--color-text-faint)" }}>No storyboard frames found in S4.</div>
    )
  }

  return (
    <>
      <div
        style={{
          display: "grid",
          gridAutoFlow: "column",
          gridAutoColumns: "minmax(96px, 1fr)",
          gap: 4,
          overflowX: "auto",
          paddingBottom: 4,
          // Smushed: every frame visible at a glance, fixed 16:9 ratio.
        }}
      >
        {files.map(f => (
          <button
            key={f.filename}
            type="button"
            onClick={() => setOpenFile(f.filename)}
            aria-label={`Open ${f.filename}`}
            title={f.filename}
            style={{
              padding: 0,
              border: "1px solid var(--color-border)",
              background: "var(--color-base)",
              borderRadius: 3,
              aspectRatio: "16 / 9",
              overflow: "hidden",
              cursor: "zoom-in",
              position: "relative",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={storyboardImageUrl(sceneId, f.filename)}
              alt={f.filename}
              loading="lazy"
              decoding="async"
              style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            />
          </button>
        ))}
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4, fontVariantNumeric: "tabular-nums" }}>
        {files.length} frame{files.length === 1 ? "" : "s"} · click to expand
      </div>
      {openFile && (
        <ThumbnailLightbox
          src={storyboardImageUrl(sceneId, openFile, { full: true })}
          alt={`${sceneId} ${openFile}`}
          onClose={() => setOpenFile(null)}
        />
      )}
    </>
  )
}

function SceneThumbnail({
  sceneId,
  hasThumbnail,
  hasFolder,
  failed,
  onError,
  onRetry,
}: {
  sceneId: string
  hasThumbnail: boolean
  /**
   * True when the scene has a resolved MEGA folder. Even if
   * has_thumbnail is flagged true, a missing folder means the thumbnail
   * endpoint has nothing to serve — retry will always fail. Treat as
   * "none yet" instead of showing a Retry button that can't recover.
   */
  hasFolder: boolean
  failed: boolean
  onError: () => void
  onRetry: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  const frameStyle: React.CSSProperties = {
    width: THUMB_WIDTH,
    aspectRatio: "16 / 9",
    borderRadius: 3,
    border: "1px solid var(--color-border)",
    background: "var(--color-base)",
    flexShrink: 0,
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  }

  // No thumbnail flagged, OR the flag is stale and there's no MEGA
  // folder yet — either way there's nothing to load, so don't bait a
  // retry click that can't succeed.
  if (!hasThumbnail || !hasFolder) {
    const title = !hasFolder
      ? "No MEGA folder yet — create the folder first, then scan"
      : "No thumbnail synced yet"
    return (
      <div style={frameStyle} title={title}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, color: "var(--color-text-faint)" }}>
          <ImageOff size={16} aria-hidden="true" />
          <span style={{ fontSize: 9, letterSpacing: "0.04em", textTransform: "uppercase" }}>None</span>
        </div>
      </div>
    )
  }

  if (failed) {
    return (
      <div
        style={{ ...frameStyle, borderColor: "color-mix(in srgb, var(--color-warn) 30%, transparent)" }}
        title="Thumbnail exists but could not load — click to retry"
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, color: "var(--color-warn)" }}>
          <ImageOff size={14} aria-hidden="true" />
          <button
            onClick={onRetry}
            style={{
              padding: "1px 6px", borderRadius: 2, fontSize: 9, cursor: "pointer",
              background: "color-mix(in srgb, var(--color-warn) 12%, transparent)",
              color: "var(--color-warn)",
              border: "1px solid color-mix(in srgb, var(--color-warn) 30%, transparent)",
            }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        aria-label={`Expand ${sceneId} thumbnail`}
        title="Click to expand"
        style={{
          ...frameStyle,
          padding: 0,
          cursor: "zoom-in",
          position: "relative",
        }}
        className="scene-thumbnail-trigger"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={thumbnailUrl(sceneId)}
          alt={`${sceneId} thumbnail`}
          loading="lazy"
          decoding="async"
          onError={onError}
          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        />
        <span
          aria-hidden="true"
          className="scene-thumbnail-zoom"
          style={{
            position: "absolute",
            top: 4, right: 4,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 20, height: 20,
            borderRadius: 3,
            background: "rgba(0,0,0,0.55)",
            color: "#fff",
            opacity: 0,
            transition: "opacity 140ms ease-out",
            pointerEvents: "none",
          }}
        >
          <Maximize2 size={11} />
        </span>
        <style jsx>{`
          .scene-thumbnail-trigger:hover .scene-thumbnail-zoom,
          .scene-thumbnail-trigger:focus-visible .scene-thumbnail-zoom { opacity: 1; }
        `}</style>
      </button>
      {expanded && (
        <ThumbnailLightbox
          src={thumbnailUrl(sceneId, { full: true })}
          alt={`${sceneId} thumbnail (full size)`}
          onClose={() => setExpanded(false)}
        />
      )}
    </>
  )
}

// ─── Lightbox: click thumbnail anywhere to view full size ───────────────────

function ThumbnailLightbox({
  src,
  alt,
  onClose,
}: {
  src: string
  alt: string
  onClose: () => void
}) {
  // Portal to <body> so the lightbox escapes the parent modal's
  // backdrop-filter containing block — otherwise position:fixed gets
  // re-anchored to the modal and the dark overlay only covers the modal,
  // not the full viewport.
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      // Capture-phase + stopImmediatePropagation so the parent modal's
      // own ESC handler doesn't also fire — otherwise one Escape closes
      // both the lightbox and the underlying scene modal.
      e.stopImmediatePropagation()
      onClose()
    }
    window.addEventListener("keydown", handleKey, { capture: true })
    return () => window.removeEventListener("keydown", handleKey, { capture: true })
  }, [onClose])

  if (!mounted || typeof document === "undefined") return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "4vh 4vw",
        background: "rgba(0, 0, 0, 0.86)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        cursor: "zoom-out",
        animation: "thumbnail-lightbox-fade 160ms ease-out",
      }}
    >
      <style>{`
        @keyframes thumbnail-lightbox-fade {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: "100%",
          maxHeight: "100%",
          objectFit: "contain",
          borderRadius: 4,
          boxShadow: "0 24px 60px -12px rgba(0,0,0,0.7)",
          cursor: "default",
        }}
      />
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          width: 36,
          height: 36,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
          background: "rgba(255,255,255,0.08)",
          color: "#fff",
          border: "1px solid rgba(255,255,255,0.18)",
          cursor: "pointer",
        }}
      >
        <X size={16} />
      </button>
    </div>,
    document.body,
  )
}

// ---------------------------------------------------------------------------
// Editable field sub-component
// ---------------------------------------------------------------------------

interface EditableFieldProps {
  label: string
  value: string
  editing: boolean
  editValue: string
  onEdit: () => void
  onCancel: () => void
  onChange: (val: string) => void
  onSave: () => void
  saving: boolean
  saveMsg: string
  multiline?: boolean
  extra?: React.ReactNode
}

function EditableField({
  label, value, editing, editValue, onEdit, onCancel, onChange, onSave, saving, saveMsg, multiline, extra,
}: EditableFieldProps) {
  const textareaRef = useRef<HTMLTextAreaElement | HTMLInputElement>(null)
  useEffect(() => {
    if (editing) {
      // Focus + caret at end
      const t = setTimeout(() => {
        const el = textareaRef.current
        if (el) {
          el.focus()
          if ("setSelectionRange" in el) {
            const len = el.value.length
            el.setSelectionRange(len, len)
          }
        }
      }, 40)
      return () => clearTimeout(t)
    }
  }, [editing])

  const dirty = editing && editValue !== value

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <FieldLabel>{label}</FieldLabel>
          {dirty && (
            <span style={{ fontSize: 9, fontWeight: 600, color: "var(--color-warn)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
              · Unsaved
            </span>
          )}
        </div>
        {!editing && (
          <button
            onClick={onEdit}
            className="transition-colors hover:opacity-80"
            style={{ fontSize: 11, color: "var(--color-text-muted)", background: "none", border: "none", padding: 0, cursor: "pointer" }}
          >
            Edit
          </button>
        )}
      </div>
      {editing ? (
        <div>
          {multiline ? (
            <textarea
              ref={textareaRef as React.RefObject<HTMLTextAreaElement>}
              value={editValue}
              onChange={(e) => onChange(e.target.value)}
              rows={3}
              style={{
                width: "100%",
                borderRadius: 3,
                padding: "6px 8px",
                fontSize: 11,
                outline: "none",
                resize: "vertical",
                background: "var(--color-base)",
                border: `1px solid ${dirty ? "color-mix(in srgb, var(--color-warn) 40%, transparent)" : "var(--color-border)"}`,
                color: "var(--color-text)",
                lineHeight: 1.5,
                fontFamily: "var(--font-sans)",
              }}
            />
          ) : (
            <input
              ref={textareaRef as React.RefObject<HTMLInputElement>}
              type="text"
              value={editValue}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") onSave() }}
              style={{
                width: "100%",
                borderRadius: 3,
                padding: "6px 8px",
                fontSize: 11,
                outline: "none",
                background: "var(--color-base)",
                border: `1px solid ${dirty ? "color-mix(in srgb, var(--color-warn) 40%, transparent)" : "var(--color-border)"}`,
                color: "var(--color-text)",
              }}
            />
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 5 }}>
            <button
              onClick={onSave}
              disabled={saving || !dirty}
              className="rounded font-medium"
              style={{
                padding: "3px 10px",
                fontSize: 11,
                background: "var(--color-lime)",
                color: "#000",
                border: "none",
                cursor: (saving || !dirty) ? "not-allowed" : "pointer",
                opacity: (saving || !dirty) ? 0.4 : 1,
              }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={onCancel}
              className="rounded"
              style={{
                padding: "3px 8px",
                fontSize: 11,
                color: "var(--color-text-muted)",
                background: "none",
                border: "none",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            {saveMsg && (
              <span style={{ fontSize: 10, color: saveMsg === "Saved" ? "var(--color-ok)" : "var(--color-err)" }}>
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      ) : (
        <div
          className="rounded"
          style={{
            padding: "6px 10px",
            fontSize: 11,
            color: value ? "var(--color-text)" : "var(--color-text-faint)",
            background: "var(--color-base)",
            border: "1px solid var(--color-border)",
            minHeight: multiline ? 40 : undefined,
            lineHeight: 1.5,
          }}
        >
          {value || "—"}
        </div>
      )}
      {extra}
    </div>
  )
}
