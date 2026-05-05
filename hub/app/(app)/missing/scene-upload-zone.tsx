"use client"

import { useState, useRef, useCallback, type DragEvent, type ChangeEvent } from "react"
import { UploadCloud, X, Check, AlertCircle } from "lucide-react"
import { uploadFile, type UploadProgress } from "@/lib/upload-multipart"
import { classify, resolveStudio, type Subfolder, SUBFOLDERS, formatBytes } from "@/lib/upload-classifier"
import { useIdToken } from "@/hooks/use-id-token"
import { revalidateAfterWrite } from "@/lib/cache-actions"
import { TAG_SCENES } from "@/lib/cache-tags"

const ALL_SUBFOLDERS: Subfolder[] = SUBFOLDERS

type FileSlot = {
  file: File
  subfolder: Subfolder
  filename: string
  status: "pending" | "uploading" | "done" | "error"
  progress: UploadProgress | null
  error?: string
  controller?: AbortController
}

/**
 * Compact dropzone for the Grail Assets modal. The scene_id and studio
 * are locked to the open scene — users only choose the subfolder (auto-
 * detected from the filename, overrideable via a dropdown). Uploads run
 * via the same multipart helper the dedicated /uploads page uses.
 *
 * Once an upload completes, we call onUploaded() so the parent can
 * refetch the scene and update the asset tiles.
 */
export function SceneUploadZone({
  sceneId,
  studio,
  idToken: serverIdToken,
  onUploaded,
}: {
  sceneId: string
  studio: string
  idToken?: string
  onUploaded: (subfolder: Subfolder) => void
}) {
  const idToken = useIdToken(serverIdToken)
  const [slots, setSlots] = useState<FileSlot[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const studioCode = resolveStudio(studio)

  const addFiles = useCallback((files: FileList | File[]) => {
    const next: FileSlot[] = []
    for (const file of Array.from(files)) {
      const decision = classify(file)
      const subfolder: Subfolder = decision.subfolder ?? "Photos"
      next.push({
        file,
        subfolder,
        filename: file.name,
        status: "pending",
        progress: null,
      })
    }
    setSlots(prev => [...prev, ...next])
  }, [])

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files.length) addFiles(e.target.files)
    e.target.value = ""  // reset so picking the same file again re-fires
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }

  function updateSlot(idx: number, patch: Partial<FileSlot>) {
    setSlots(prev => prev.map((s, i) => i === idx ? { ...s, ...patch } : s))
  }

  async function startUpload(idx: number) {
    if (!idToken) {
      updateSlot(idx, { status: "error", error: "Not signed in" })
      return
    }
    if (!studioCode) {
      updateSlot(idx, { status: "error", error: `Unknown studio: ${studio}` })
      return
    }
    const slot = slots[idx]
    if (!slot || slot.status === "uploading" || slot.status === "done") return

    const controller = new AbortController()
    updateSlot(idx, { status: "uploading", controller, error: undefined })

    const result = await uploadFile({
      file: slot.file,
      studio: studioCode,
      scene_id: sceneId,
      subfolder: slot.subfolder,
      filename: slot.filename,
      idToken,
      onProgress: (p) => updateSlot(idx, { progress: p }),
      signal: controller.signal,
    })

    if (result.ok) {
      updateSlot(idx, { status: "done" })
      try {
        await revalidateAfterWrite([TAG_SCENES])
      } catch { /* best-effort */ }
      onUploaded(slot.subfolder)
    } else {
      updateSlot(idx, { status: "error", error: result.error ?? "Upload failed" })
    }
  }

  function cancelUpload(idx: number) {
    const slot = slots[idx]
    slot?.controller?.abort()
    setSlots(prev => prev.filter((_, i) => i !== idx))
  }

  function startAllPending() {
    slots.forEach((s, i) => { if (s.status === "pending") void startUpload(i) })
  }

  const pendingCount = slots.filter(s => s.status === "pending").length

  return (
    <div>
      {/* Dropzone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click() }}
        style={{
          padding: "14px",
          borderRadius: 6,
          border: `1.5px dashed ${dragOver ? "var(--color-lime)" : "var(--color-border)"}`,
          background: dragOver ? "color-mix(in srgb, var(--color-lime) 6%, transparent)" : "var(--color-base)",
          textAlign: "center",
          cursor: "pointer",
          transition: "border-color 140ms ease, background-color 140ms ease",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          onChange={onInputChange}
          style={{ display: "none" }}
        />
        <UploadCloud size={18} style={{ color: dragOver ? "var(--color-lime)" : "var(--color-text-muted)", marginBottom: 4 }} aria-hidden="true" />
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)" }}>
          Drop files or click to browse
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>
          Files upload to <span className="font-mono">{sceneId}</span> · subfolder auto-detected
        </div>
      </div>

      {/* File queue */}
      {slots.length > 0 && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
          {slots.map((s, i) => {
            const pct = s.progress && s.progress.bytesTotal
              ? Math.min(100, Math.round((s.progress.bytesUploaded / s.progress.bytesTotal) * 100))
              : 0
            const phaseLabel =
              s.status === "done"  ? "Uploaded" :
              s.status === "error" ? (s.error ?? "Error") :
              s.status === "uploading" ? `Uploading… ${pct}%` :
              "Pending"
            const color =
              s.status === "done"  ? "var(--color-ok)" :
              s.status === "error" ? "var(--color-err)" :
              s.status === "uploading" ? "var(--color-lime)" :
              "var(--color-text-muted)"
            return (
              <div
                key={`${s.file.name}-${i}`}
                style={{
                  padding: "8px 10px",
                  borderRadius: 4,
                  background: "var(--color-base)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "var(--color-text)", fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.file.name}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                      <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                        {formatBytes(s.file.size)} ·
                      </span>
                      <select
                        value={s.subfolder}
                        onChange={(e) => updateSlot(i, { subfolder: e.target.value as Subfolder })}
                        disabled={s.status !== "pending"}
                        style={{
                          fontSize: 10,
                          padding: "1px 4px",
                          background: "var(--color-base)",
                          color: "var(--color-text)",
                          border: "1px solid var(--color-border)",
                          borderRadius: 3,
                          cursor: s.status === "pending" ? "pointer" : "not-allowed",
                        }}
                      >
                        {ALL_SUBFOLDERS.map(sub => (
                          <option key={sub} value={sub}>{sub}</option>
                        ))}
                      </select>
                      <span style={{ fontSize: 10, fontWeight: 600, color, marginLeft: "auto" }}>
                        {s.status === "done" && <Check size={9} aria-hidden="true" style={{ display: "inline", marginRight: 2 }} />}
                        {s.status === "error" && <AlertCircle size={9} aria-hidden="true" style={{ display: "inline", marginRight: 2 }} />}
                        {phaseLabel}
                      </span>
                    </div>
                    {s.status === "uploading" && (
                      <div style={{ marginTop: 4, height: 2, background: "var(--color-border)", borderRadius: 1, overflow: "hidden" }}>
                        <div style={{ width: "100%", height: "100%", background: "var(--color-lime)", transformOrigin: "left", transform: `scaleX(${pct / 100})`, transition: "transform 120ms linear" }} />
                      </div>
                    )}
                  </div>
                  {s.status !== "uploading" && s.status !== "done" && (
                    <button
                      onClick={() => cancelUpload(i)}
                      aria-label="Remove from queue"
                      style={{ background: "transparent", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 2 }}
                    >
                      <X size={11} />
                    </button>
                  )}
                </div>
              </div>
            )
          })}

          {pendingCount > 0 && (
            <button
              onClick={startAllPending}
              style={{
                alignSelf: "flex-start",
                padding: "5px 12px",
                borderRadius: 4,
                background: "var(--color-lime)",
                color: "#000",
                fontWeight: 700,
                fontSize: 11,
                border: "none",
                cursor: "pointer",
              }}
            >
              Upload {pendingCount} file{pendingCount === 1 ? "" : "s"}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
