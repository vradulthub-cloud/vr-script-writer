"use client"

import { useState, useEffect } from "react"
import { ArrowLeft, Wand2, FolderPlus, ImageOff } from "lucide-react"
import { api, thumbnailUrl, type Scene, type NamingIssue } from "@/lib/api"
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
  onBack: () => void
  onSceneUpdate: (updated: Scene) => void
}

export function SceneDetail({ scene: initialScene, idToken: serverToken, onBack, onSceneUpdate }: SceneDetailProps) {
  const idToken = useIdToken(serverToken)
  const client = api(idToken ?? null)
  const color = studioColor(initialScene.studio)

  const [scene, setScene] = useState(initialScene)

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

  // MEGA folder
  const [folderCreating, setFolderCreating] = useState(false)
  const [folderMsg, setFolderMsg] = useState("")

  // Thumbnail load state — server sync can claim has_thumbnail=true before the
  // MEGA proxy actually has the file, so we treat image errors as "missing"
  const [thumbFailed, setThumbFailed] = useState(false)

  // Load naming issues on mount
  useEffect(() => {
    client.scenes.namingIssues(scene.id).then((data) => {
      setNamingIssues(data.issues)
      setNamingOk(data.ok)
    }).catch((e) => {
      console.warn("[scene-detail] Failed to load naming issues:", e)
    })
  }, [scene.id])

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

  const pct = Math.round(
    (ASSET_COLS.filter((a) => scene[a.key]).length / ASSET_COLS.length) * 100,
  )

  return (
    <div>
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 mb-4 transition-colors hover:opacity-80"
        style={{ fontSize: 12, color: "var(--color-text-muted)" }}
      >
        <ArrowLeft size={13} />
        Back to grid
      </button>

      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-start gap-4">
        {/* Thumbnail — hero visual; endpoint is public per api/routers/scenes.py */}
        <SceneThumbnail
          sceneId={scene.id}
          hasThumbnail={scene.has_thumbnail}
          failed={thumbFailed}
          onError={() => setThumbFailed(true)}
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <span className="font-mono font-semibold" style={{ fontSize: 18, color }}>
              {scene.id}
            </span>
            <StudioBadge studio={scene.studio} />
            {scene.is_compilation && (
              <span
                className="rounded px-2 py-0.5"
                style={{ fontSize: 10, background: "color-mix(in srgb, var(--color-warn) 15%, transparent)", color: "var(--color-warn)" }}
              >
                Compilation
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
            {scene.performers || "No performers listed"}
            {scene.release_date && <span> &middot; {scene.release_date}</span>}
          </div>

          {/* Progress bar */}
          <div className="flex items-center gap-2 mt-3">
            <div className="rounded-full overflow-hidden" style={{ width: 120, height: 4, background: "var(--color-border)" }}>
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pct}%`,
                  background: pct === 100 ? "var(--color-ok)" : pct >= 60 ? "var(--color-warn)" : "var(--color-err)",
                }}
              />
            </div>
            <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{pct}% complete</span>
          </div>
        </div>
      </div>

      {/* Asset status */}
      <div className="flex gap-3 mb-6 flex-wrap">
        {ASSET_COLS.map((col) => (
          <div
            key={col.key}
            className="rounded px-3 py-2"
            style={{
              background: "var(--color-surface)",
              border: `1px solid ${scene[col.key] ? "color-mix(in srgb, var(--color-ok) 30%, transparent)" : "var(--color-border)"}`,
              minWidth: 100,
            }}
          >
            <div style={{ fontSize: 15, marginBottom: 2 }}>
              {scene[col.key] ? (
                <span style={{ color: "var(--color-ok)" }}>&#10003;</span>
              ) : (
                <span style={{ color: "var(--color-err)" }}>&#10007;</span>
              )}
            </div>
            <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{col.label}</div>
          </div>
        ))}
      </div>

      {/* Editable fields */}
      <div className="space-y-4">
        {/* Title */}
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
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={generateTitle}
                disabled={generating}
                className="flex items-center gap-1.5 rounded px-2.5 py-1 text-xs transition-colors"
                style={{
                  background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                  color: "var(--color-lime)",
                  border: "1px solid color-mix(in srgb, var(--color-lime) 25%, transparent)",
                  opacity: generating ? 0.5 : 1,
                }}
              >
                <Wand2 size={11} />
                {generating ? "Generating..." : "Generate Title"}
              </button>
              {genTitle && (
                <>
                  <span style={{ fontSize: 12, color: "var(--color-text)" }}>{genTitle}</span>
                  <button
                    onClick={applyGenTitle}
                    className="rounded px-2 py-0.5 text-xs font-medium"
                    style={{ background: "var(--color-lime)", color: "#000" }}
                  >
                    Apply
                  </button>
                </>
              )}
            </div>
          }
        />

        {/* Categories */}
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

        {/* Tags */}
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

        {/* Plot (read-only) */}
        {scene.plot && (
          <div>
            <div className="mb-1" style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Plot
            </div>
            <div
              className="rounded px-3 py-2"
              style={{ fontSize: 12, color: "var(--color-text-muted)", background: "var(--color-surface)", border: "1px solid var(--color-border)", lineHeight: 1.5 }}
            >
              {scene.plot}
            </div>
          </div>
        )}
      </div>

      {/* Naming validation */}
      {namingOk !== null && (
        <div className="mt-6">
          <div className="mb-1" style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Naming Validation
          </div>
          {namingOk ? (
            <div className="rounded px-3 py-2" style={{ fontSize: 12, color: "var(--color-ok)", background: "color-mix(in srgb, var(--color-ok) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--color-ok) 20%, transparent)" }}>
              All naming conventions OK
            </div>
          ) : (
            <div className="rounded px-3 py-2 space-y-1" style={{ background: "color-mix(in srgb, var(--color-err) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--color-err) 20%, transparent)" }}>
              {namingIssues?.map((issue, i) => (
                <div key={i} style={{ fontSize: 12, color: "var(--color-err)" }}>
                  <span className="font-mono" style={{ fontSize: 11 }}>{issue.file}</span> — {issue.issue}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* MEGA folder */}
      {!scene.mega_path && (
        <div className="mt-6">
          <button
            onClick={createFolder}
            disabled={folderCreating}
            className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs transition-colors"
            style={{
              background: "var(--color-surface)",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              opacity: folderCreating ? 0.5 : 1,
            }}
          >
            <FolderPlus size={13} />
            {folderCreating ? "Creating..." : "Create MEGA Folder"}
          </button>
          {folderMsg && (
            <span className="ml-2" style={{ fontSize: 11, color: folderMsg.includes("queued") ? "var(--color-ok)" : "var(--color-err)" }}>
              {folderMsg}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scene thumbnail sub-component
// ---------------------------------------------------------------------------

const THUMB_WIDTH = 240

function SceneThumbnail({
  sceneId,
  hasThumbnail,
  failed,
  onError,
}: {
  sceneId: string
  hasThumbnail: boolean
  failed: boolean
  onError: () => void
}) {
  const frameStyle: React.CSSProperties = {
    width: THUMB_WIDTH,
    aspectRatio: "16 / 9",
    borderRadius: 4,
    border: "1px solid var(--color-border)",
    background: "var(--color-surface)",
    flexShrink: 0,
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  }

  if (!hasThumbnail || failed) {
    return (
      <div
        style={frameStyle}
        title={failed ? "Thumbnail could not be loaded" : "No thumbnail synced yet"}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
            color: "var(--color-text-faint)",
          }}
        >
          <ImageOff size={20} aria-hidden="true" />
          <span style={{ fontSize: 10, letterSpacing: "0.04em", textTransform: "uppercase" }}>
            No thumbnail
          </span>
        </div>
      </div>
    )
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={thumbnailUrl(sceneId)}
      alt={`${sceneId} thumbnail`}
      loading="lazy"
      decoding="async"
      onError={onError}
      style={{
        ...frameStyle,
        objectFit: "cover",
        display: "block",
      }}
    />
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
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          {label}
        </span>
        {!editing && (
          <button
            onClick={onEdit}
            className="text-xs transition-colors hover:opacity-80"
            style={{ color: "var(--color-text-muted)" }}
          >
            Edit
          </button>
        )}
      </div>
      {editing ? (
        <div>
          {multiline ? (
            <textarea
              value={editValue}
              onChange={(e) => onChange(e.target.value)}
              rows={3}
              className="w-full rounded px-3 py-2 text-xs outline-none resize-y"
              style={{
                background: "var(--color-base)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
                lineHeight: 1.5,
              }}
            />
          ) : (
            <input
              type="text"
              value={editValue}
              onChange={(e) => onChange(e.target.value)}
              className="w-full rounded px-3 py-2 text-xs outline-none"
              style={{
                background: "var(--color-base)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
              autoFocus
            />
          )}
          <div className="flex items-center gap-2 mt-1.5">
            <button
              onClick={onSave}
              disabled={saving}
              className="rounded px-3 py-1 text-xs font-medium"
              style={{ background: "var(--color-lime)", color: "#000", opacity: saving ? 0.5 : 1 }}
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={onCancel}
              className="rounded px-2 py-1 text-xs"
              style={{ color: "var(--color-text-muted)" }}
            >
              Cancel
            </button>
            {saveMsg && (
              <span style={{ fontSize: 11, color: saveMsg === "Saved" ? "var(--color-ok)" : "var(--color-err)" }}>
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      ) : (
        <div
          className="rounded px-3 py-2"
          style={{
            fontSize: 12,
            color: value ? "var(--color-text)" : "var(--color-text-faint)",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            minHeight: multiline ? 48 : undefined,
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
