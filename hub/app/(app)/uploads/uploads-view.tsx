"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { RotateCw } from "lucide-react"
import { UploadCloud, Pencil, X, Check, AlertCircle, Copy, Link as LinkIcon } from "lucide-react"
import { uploadFile, cleanupUpload, getResumableProgress, type UploadProgress } from "@/lib/upload-multipart"
import {
  classify,
  formatBytes,
  normalizeSceneId,
  resolveStudio,
  STUDIO_BUCKETS,
  SUBFOLDERS,
  type RoutingDecision,
  type StudioCode,
  type Subfolder,
} from "@/lib/upload-classifier"
import { api, type UploadHistoryRow } from "@/lib/api"

type RowState = "pending" | "queued" | "uploading" | "done" | "error" | "aborted"

interface UploadRow {
  id: string
  file: File
  decision: RoutingDecision
  state: RowState
  progress: UploadProgress | null
  controller: AbortController | null
  result?: { key: string; presigned_url: string }
  error?: string
  /** Resumable progress detected on the row (e.g. after a failure). */
  resumable?: { partsCompleted: number; partsTotal: number; bytesUploaded: number } | null
}

const studioColorVar: Record<StudioCode, string> = {
  FPVR: "var(--color-fpvr)",
  VRH:  "var(--color-vrh)",
  VRA:  "var(--color-vra)",
  NJOI: "var(--color-njoi)",
}

function rowKey(file: File): string {
  return `${file.name}|${file.size}|${file.lastModified}|${Math.random().toString(36).slice(2, 8)}`
}

function relativeTime(tsSec: number): string {
  const diff = Math.max(0, Date.now() / 1000 - tsSec)
  if (diff < 60)        return `${Math.round(diff)}s ago`
  if (diff < 3600)      return `${Math.round(diff / 60)}m ago`
  if (diff < 86400)     return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

// Cap concurrent file uploads. Each in-flight upload itself runs up to 4
// parallel part PUTs, so MAX_CONCURRENT_UPLOADS × 4 ≈ S4 fan-out.
// 2 keeps us within MEGA S4's polite rate ceiling and stays under most
// browsers' 6-conn-per-origin cap when paired with the API + S4 hostnames.
const MAX_CONCURRENT_UPLOADS = 2

export function UploadsView({
  idToken,
  initialHistory,
}: {
  idToken: string
  initialHistory: UploadHistoryRow[]
}) {
  const [rows, setRows] = useState<UploadRow[]>([])
  const [history, setHistory] = useState<UploadHistoryRow[]>(initialHistory)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const folderInputRef = useRef<HTMLInputElement | null>(null)

  // Queue + worker-pool state. Refs so handlers don't capture stale snapshots
  // and we don't churn renders on every dequeue. Queue stores row references
  // directly because reading rows from `setRows(prev => ...)` is async (React
  // batches updater callbacks) and would race the dequeue.
  const uploadQueueRef = useRef<UploadRow[]>([])
  const inFlightRef = useRef<Set<string>>(new Set())

  const client = useMemo(() => api(idToken), [idToken])

  const refreshHistory = useCallback(async () => {
    try {
      const h = await client.uploads.history(50)
      setHistory(h)
    } catch {
      // ignore
    }
  }, [client])

  // ── Adding files ───────────────────────────────────────────────────────
  const addFiles = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files)
    const fresh: UploadRow[] = arr.map(file => ({
      id: rowKey(file),
      file,
      decision: classify(file),
      state: "pending",
      progress: null,
      controller: null,
    }))
    setRows(prev => [...prev, ...fresh])
  }, [])

  // Drag-and-drop with directory recursion (DataTransfer items API).
  const onDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const items = e.dataTransfer?.items
    if (items && items.length && typeof items[0].webkitGetAsEntry === "function") {
      const collected: File[] = []
      const promises: Promise<void>[] = []
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.()
        if (entry) promises.push(walkEntry(entry, collected))
      }
      await Promise.all(promises)
      if (collected.length) addFiles(collected)
      return
    }
    if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files)
  }, [addFiles])

  // ── Editing destination per row ─────────────────────────────────────────
  const updateDecision = useCallback((id: string, patch: Partial<RoutingDecision>) => {
    setRows(prev => prev.map(r => {
      if (r.id !== id) return r
      const next = { ...r.decision, ...patch }
      // Recompute confidence from the patch — if all three pieces are present,
      // bump to 1.0 unless the user already lowered it.
      if (next.studio && next.scene_id && next.subfolder && r.decision.confidence < 1) {
        next.confidence = 1
        next.reason = "Manually routed"
      }
      return { ...r, decision: next }
    }))
  }, [])

  const removeRow = useCallback((id: string) => {
    // Drop from the queue if it never started, abort if it's mid-upload.
    uploadQueueRef.current = uploadQueueRef.current.filter(r => r.id !== id)
    let target: UploadRow | undefined
    setRows(prev => {
      target = prev.find(x => x.id === id)
      target?.controller?.abort()
      return prev.filter(x => x.id !== id)
    })
    // If the row was an unresumed failure with saved partial progress, tell
    // S4 to abandon the multipart and free the parts. Best-effort.
    if (target && target.state === "error" && target.decision.studio
        && target.decision.scene_id && target.decision.subfolder) {
      void cleanupUpload(target.file, {
        studio:    target.decision.studio,
        scene_id:  target.decision.scene_id,
        subfolder: target.decision.subfolder,
        filename:  target.decision.filename,
        idToken,
      })
    }
  }, [idToken])

  // ── Uploading ──────────────────────────────────────────────────────────
  // Run a single file end-to-end. Caller is responsible for queue accounting.
  const runUpload = useCallback(async (row: UploadRow) => {
    if (!row.decision.studio || !row.decision.scene_id || !row.decision.subfolder) return
    const controller = new AbortController()
    setRows(prev => prev.map(r => r.id === row.id ? { ...r, state: "uploading", controller } : r))
    const result = await uploadFile({
      file:       row.file,
      studio:     row.decision.studio,
      scene_id:   row.decision.scene_id,
      subfolder:  row.decision.subfolder,
      filename:   row.decision.filename,
      idToken,
      signal:     controller.signal,
      onProgress: (p) => {
        setRows(prev => prev.map(r => r.id === row.id ? { ...r, progress: p } : r))
      },
    })
    setRows(prev => prev.map(r => {
      if (r.id !== row.id) return r
      if (result.ok && result.key) {
        return { ...r, state: "done", controller: null, result: { key: result.key, presigned_url: result.presignedUrl ?? "" } }
      }
      return { ...r, state: result.error === "aborted" ? "aborted" : "error", controller: null, error: result.error }
    }))
    if (result.ok) {
      void refreshHistory()
    }
  }, [idToken, refreshHistory])

  // Worker-pool drain: pull rows off the queue and run up to
  // MAX_CONCURRENT_UPLOADS in parallel. Each completion triggers another pump.
  const pumpQueue = useCallback(() => {
    while (inFlightRef.current.size < MAX_CONCURRENT_UPLOADS) {
      const next = uploadQueueRef.current.shift()
      if (!next) return
      // removeRow filters cancelled rows out of the queue, so anything left
      // here is fair game — run it.
      inFlightRef.current.add(next.id)
      void runUpload(next).finally(() => {
        inFlightRef.current.delete(next.id)
        pumpQueue()
      })
    }
  }, [runUpload])

  // Helper: is this row already queued or in-flight?
  const isAlreadyScheduled = (id: string) =>
    uploadQueueRef.current.some(r => r.id === id) || inFlightRef.current.has(id)

  // Single-row trigger — used by per-row Upload button and "Upload all ready".
  const startUpload = useCallback((row: UploadRow) => {
    if (!row.decision.studio || !row.decision.scene_id || !row.decision.subfolder) return
    if (isAlreadyScheduled(row.id)) return
    // Mark as queued in UI so user sees it move out of "ready".
    setRows(prev => prev.map(r => r.id === row.id ? { ...r, state: "queued" } : r))
    uploadQueueRef.current.push(row)
    pumpQueue()
  }, [pumpQueue])

  const uploadAllReady = useCallback(() => {
    const ready = rows.filter(r => r.state === "pending" && r.decision.confidence >= 1)
    if (ready.length === 0) return
    setRows(prev => prev.map(r =>
      ready.some(x => x.id === r.id) ? { ...r, state: "queued" } : r
    ))
    for (const r of ready) {
      if (!isAlreadyScheduled(r.id)) uploadQueueRef.current.push(r)
    }
    pumpQueue()
  }, [rows, pumpQueue])

  // Retry a failed row — re-enqueue it. uploadFile() will see saved IndexedDB
  // state for this (file fingerprint + destination) and skip already-uploaded
  // parts, so progress resumes from where it failed.
  const retryUpload = useCallback((row: UploadRow) => {
    if (!row.decision.studio || !row.decision.scene_id || !row.decision.subfolder) return
    if (isAlreadyScheduled(row.id)) return
    setRows(prev => prev.map(r => r.id === row.id
      ? { ...r, state: "queued", error: undefined, progress: null }
      : r))
    uploadQueueRef.current.push(row)
    pumpQueue()
  }, [pumpQueue])

  // After a row enters "error", check IndexedDB to see how much progress was
  // saved — used by the UI to show "Resume from N%" on the row.
  useEffect(() => {
    const errored = rows.filter(r => r.state === "error" && r.resumable === undefined)
    if (errored.length === 0) return
    let cancelled = false
    void (async () => {
      for (const r of errored) {
        if (!r.decision.scene_id || !r.decision.subfolder) continue
        const resumable = await getResumableProgress(r.file, {
          scene_id:  r.decision.scene_id,
          subfolder: r.decision.subfolder,
          filename:  r.decision.filename,
        })
        if (cancelled) return
        setRows(prev => prev.map(x => x.id === r.id ? { ...x, resumable } : x))
      }
    })()
    return () => { cancelled = true }
  }, [rows])

  // ── Render ─────────────────────────────────────────────────────────────
  const pending = rows.filter(r => r.state === "pending")
  // Queued rows are sitting in the worker-pool waiting for a slot — render
  // them alongside actively-uploading rows so the user sees the full pipeline.
  const active = rows.filter(r => r.state === "uploading" || r.state === "queued")
  const completed = rows.filter(r => r.state === "done" || r.state === "error" || r.state === "aborted")
  const readyCount = pending.filter(r => r.decision.confidence >= 1).length

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
          Asset Pipeline · Direct to MEGA S4
        </div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 32, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 4 }}>
          Uploads
        </h1>
        <p style={{ color: "var(--color-text-muted)", fontSize: 13, marginTop: 4 }}>
          Drop files. We&rsquo;ll route each one to the right scene and folder. Review before clicking Upload.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        style={{
          border: `1.5px dashed ${dragActive ? "var(--color-lime)" : "var(--color-border)"}`,
          background: dragActive ? "rgba(190,214,47,0.04)" : "var(--color-surface)",
          padding: "44px 24px",
          textAlign: "center",
          transition: "all 120ms ease",
          cursor: "pointer",
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <UploadCloud size={28} style={{ color: dragActive ? "var(--color-lime)" : "var(--color-text-muted)", margin: "0 auto" }} />
        <div style={{ marginTop: 10, fontSize: 14, fontWeight: 500 }}>
          Drop files or folders here
        </div>
        <div style={{ marginTop: 4, fontSize: 12, color: "var(--color-text-muted)" }}>
          Or <button type="button" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }} style={{ color: "var(--color-lime)", fontWeight: 500 }}>choose files</button>
          {" · "}
          <button type="button" onClick={(e) => { e.stopPropagation(); folderInputRef.current?.click() }} style={{ color: "var(--color-lime)", fontWeight: 500 }}>choose folder</button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: "none" }}
          onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = "" }}
        />
        <input
          ref={folderInputRef}
          type="file"
          // @ts-expect-error — webkitdirectory not in standard FileInput types
          webkitdirectory=""
          directory=""
          multiple
          style={{ display: "none" }}
          onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = "" }}
        />
      </div>

      {/* Pending */}
      {pending.length > 0 && (
        <Block
          title="Pending"
          count={pending.length}
          actions={
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{readyCount} ready</span>
              <button
                type="button"
                disabled={readyCount === 0}
                onClick={uploadAllReady}
                className="ec-btn molten"
                style={{ opacity: readyCount === 0 ? 0.4 : 1, padding: "6px 14px", fontSize: 12 }}
              >
                Upload all ready
              </button>
            </div>
          }
        >
          {pending.map(row => (
            <PendingRow
              key={row.id}
              row={row}
              onChange={(patch) => updateDecision(row.id, patch)}
              onRemove={() => removeRow(row.id)}
              onUpload={() => startUpload(row)}
            />
          ))}
        </Block>
      )}

      {/* Active */}
      {active.length > 0 && (
        <Block title="Active" count={active.length}>
          {active.map(row => (
            <ActiveRow
              key={row.id}
              row={row}
              onCancel={() => row.controller?.abort()}
            />
          ))}
        </Block>
      )}

      {/* Completed in this session */}
      {completed.length > 0 && (
        <Block title="Just finished" count={completed.length}>
          {completed.map(row => (
            <CompletedRow
              key={row.id}
              row={row}
              onDismiss={() => removeRow(row.id)}
              onRetry={() => retryUpload(row)}
            />
          ))}
        </Block>
      )}

      {/* Recent uploads — server-backed audit log */}
      <Block title="Recent uploads" count={history.length}>
        {history.length === 0
          ? <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-faint)", fontSize: 13 }}>No uploads yet.</div>
          : history.map((h, i) => <HistoryRow key={i} row={h} idToken={idToken} />)
        }
      </Block>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function Block({
  title,
  count,
  actions,
  children,
}: {
  title: string
  count: number
  actions?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="ec-block">
      <header>
        <h2>
          {title} <span className="num">{count}</span>
        </h2>
        {actions && <div className="act">{actions}</div>}
      </header>
      <div>{children}</div>
    </section>
  )
}

function PendingRow({
  row,
  onChange,
  onRemove,
  onUpload,
}: {
  row: UploadRow
  onChange: (patch: Partial<RoutingDecision>) => void
  onRemove: () => void
  onUpload: () => void
}) {
  const [editing, setEditing] = useState(row.decision.confidence < 1)
  const ready = row.decision.confidence >= 1
  const studio = row.decision.studio
  const tint = studio ? studioColorVar[studio] : "var(--color-text-faint)"

  return (
    <div
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 16, padding: "12px 16px",
        borderBottom: "1px solid var(--color-border-subtle)",
        borderLeft: `3px solid ${tint}`,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {ready
            ? <Check size={14} style={{ color: "var(--color-ok)" }} />
            : <AlertCircle size={14} style={{ color: "var(--color-warn)" }} />
          }
          <span style={{ fontWeight: 500, fontSize: 13 }}>{row.file.name}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{formatBytes(row.file.size)}</span>
        </div>
        {editing
          ? <DestinationEditor decision={row.decision} onChange={onChange} />
          : (
            <div style={{ marginTop: 4, fontSize: 12, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
              <span style={{ color: tint, fontWeight: 600 }}>{studio?.toLowerCase() ?? "?"}</span>
              <span> / </span>
              <span>{row.decision.scene_id ?? "?"}</span>
              <span> / </span>
              <span>{row.decision.subfolder ?? "?"}</span>
              <span> / </span>
              <span>{row.decision.filename}</span>
            </div>
          )
        }
        {!ready && row.decision.reason && (
          <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-warn)" }}>
            {row.decision.reason}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={() => setEditing(e => !e)}
          className="ec-btn ghost"
          title={editing ? "Hide editor" : "Edit destination"}
          style={{ padding: "5px 8px" }}
        >
          <Pencil size={13} />
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="ec-btn ghost"
          title="Remove"
          style={{ padding: "5px 8px" }}
        >
          <X size={13} />
        </button>
        <button
          type="button"
          onClick={onUpload}
          disabled={!ready}
          className="ec-btn molten"
          style={{ opacity: ready ? 1 : 0.4, padding: "5px 14px", fontSize: 12 }}
        >
          Upload
        </button>
      </div>
    </div>
  )
}

function DestinationEditor({
  decision,
  onChange,
}: {
  decision: RoutingDecision
  onChange: (patch: Partial<RoutingDecision>) => void
}) {
  const [sceneRaw, setSceneRaw] = useState(decision.scene_id ?? "")
  return (
    <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
      <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
        <div style={{ marginBottom: 2 }}>Studio</div>
        <select
          value={decision.studio ?? ""}
          onChange={(e) => onChange({ studio: e.target.value ? (e.target.value as StudioCode) : null })}
          style={inputStyle}
        >
          <option value="">— Pick —</option>
          {Object.keys(STUDIO_BUCKETS).map(code => (
            <option key={code} value={code}>{code}</option>
          ))}
        </select>
      </label>
      <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
        <div style={{ marginBottom: 2 }}>Scene ID</div>
        <input
          type="text"
          value={sceneRaw}
          placeholder="e.g. VRH0762"
          onChange={(e) => setSceneRaw(e.target.value)}
          onBlur={() => {
            const raw = sceneRaw.trim()
            if (!raw) { onChange({ scene_id: null }); return }
            try {
              const norm = normalizeSceneId(raw)
              const studio = resolveStudio(norm.match(/^[A-Z]+/)?.[0] ?? "")
              onChange({ scene_id: norm, studio: studio ?? decision.studio })
              setSceneRaw(norm)
            } catch {
              onChange({ scene_id: null })
            }
          }}
          style={inputStyle}
        />
      </label>
      <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
        <div style={{ marginBottom: 2 }}>Subfolder</div>
        <select
          value={decision.subfolder ?? ""}
          onChange={(e) => onChange({ subfolder: (e.target.value || null) as Subfolder | null })}
          style={inputStyle}
        >
          <option value="">— Pick —</option>
          {SUBFOLDERS.map(sf => <option key={sf} value={sf}>{sf}</option>)}
        </select>
      </label>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "var(--color-base)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text)",
  padding: "6px 8px",
  fontSize: 12,
  borderRadius: 0,
}

function ActiveRow({ row, onCancel }: { row: UploadRow; onCancel: () => void }) {
  const isQueued = row.state === "queued"
  const p = row.progress
  const pct = p ? Math.min(100, Math.round((p.bytesUploaded / Math.max(1, p.bytesTotal)) * 100)) : 0
  const studio = row.decision.studio
  const tint = studio ? studioColorVar[studio] : "var(--color-text-faint)"
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 16,
        padding: "12px 16px",
        borderBottom: "1px solid var(--color-border-subtle)",
        borderLeft: `3px solid ${tint}`,
        opacity: isQueued ? 0.6 : 1,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <span style={{ fontWeight: 500, fontSize: 13 }}>{row.file.name}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            {isQueued
              ? <span style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>queued</span>
              : <>
                  {formatBytes(p?.bytesUploaded ?? 0)} / {formatBytes(row.file.size)} · {pct}%
                  {p && p.partsTotal > 0 && <> · part {p.partsCompleted}/{p.partsTotal}</>}
                </>
            }
          </span>
        </div>
        <div style={{ marginTop: 6, height: 4, background: "var(--color-base)" }}>
          <div style={{ width: `${isQueued ? 0 : pct}%`, height: 4, background: "var(--color-lime)", transition: "width 120ms ease" }} />
        </div>
        <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
          {studio?.toLowerCase()} / {row.decision.scene_id} / {row.decision.subfolder} / {row.decision.filename}
        </div>
      </div>
      <button type="button" onClick={onCancel} className="ec-btn ghost" style={{ padding: "5px 10px" }}>
        Cancel
      </button>
    </div>
  )
}

function CompletedRow({ row, onDismiss, onRetry }: {
  row: UploadRow
  onDismiss: () => void
  onRetry: () => void
}) {
  const ok = row.state === "done"
  const studio = row.decision.studio
  const tint = studio ? studioColorVar[studio] : "var(--color-text-faint)"
  // Show resume affordance when this row failed mid-upload AND we still have
  // saved part progress in IndexedDB. uploadFile() will reuse those parts.
  const hasResume = row.state === "error" && row.resumable && row.resumable.partsCompleted > 0
  const resumePct = hasResume
    ? Math.round((row.resumable!.partsCompleted / Math.max(1, row.resumable!.partsTotal)) * 100)
    : 0
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 16,
        padding: "10px 16px",
        borderBottom: "1px solid var(--color-border-subtle)",
        borderLeft: `3px solid ${tint}`,
        opacity: ok ? 1 : 0.85,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {ok
            ? <Check size={14} style={{ color: "var(--color-ok)" }} />
            : <AlertCircle size={14} style={{ color: row.state === "aborted" ? "var(--color-text-muted)" : "var(--color-err)" }} />
          }
          <span style={{ fontSize: 13, fontWeight: 500 }}>{row.file.name}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            {row.state}
          </span>
          {hasResume && (
            <span style={{
              fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--color-lime)",
              padding: "1px 6px",
              border: "1px solid var(--color-lime)",
              borderRadius: 2,
            }}>
              Resumable · {resumePct}% saved
            </span>
          )}
        </div>
        {row.error && (
          <div style={{ marginTop: 2, fontSize: 11, color: "var(--color-err)" }}>{row.error}</div>
        )}
        {row.result?.key && (
          <div style={{ marginTop: 2, fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            {row.result.key}
          </div>
        )}
      </div>
      {row.state === "error" && (
        <button
          type="button"
          onClick={onRetry}
          className="ec-btn molten"
          style={{ padding: "5px 12px", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}
          title={hasResume ? `Resume from ${resumePct}%` : "Retry upload"}
        >
          <RotateCw size={12} />
          {hasResume ? "Resume" : "Retry"}
        </button>
      )}
      <button type="button" onClick={onDismiss} className="ec-btn ghost" style={{ padding: "5px 8px" }} title="Dismiss & abandon">
        <X size={13} />
      </button>
    </div>
  )
}

function HistoryRow({ row, idToken }: { row: UploadHistoryRow; idToken: string }) {
  void idToken
  const studio = resolveStudio(row.studio)
  const tint = studio ? studioColorVar[studio] : "var(--color-text-faint)"
  const [copied, setCopied] = useState(false)
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 16,
        padding: "10px 16px",
        borderBottom: "1px solid var(--color-border-subtle)",
        borderLeft: `3px solid ${tint}`,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "var(--color-text-muted)" }}>
          <span style={{ color: "var(--color-text-faint)" }}>{relativeTime(row.ts)}</span>
          <span>·</span>
          <span style={{ color: "var(--color-text)" }}>{row.user_name || row.user_email}</span>
          <span>·</span>
          <span style={{ fontFamily: "var(--font-mono)" }}>{row.studio.toLowerCase()} / {row.scene_id} / {row.subfolder}</span>
        </div>
        <div style={{ marginTop: 2, fontSize: 13, fontWeight: 500 }}>
          {row.filename}
          <span style={{ marginLeft: 8, fontSize: 11, color: "var(--color-text-faint)", fontWeight: 400 }}>
            {formatBytes(row.size)} · {row.mode}
          </span>
        </div>
      </div>
      <button
        type="button"
        onClick={async () => {
          // Generate a fresh presigned link via the head endpoint, but we
          // don't have a /share endpoint — for v1, copy the key path.
          await navigator.clipboard.writeText(row.key)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        }}
        className="ec-btn ghost"
        style={{ padding: "5px 10px", fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}
        title="Copy key"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? "Copied" : "Copy key"}
      </button>
    </div>
  )
}

// ── Folder-drop traversal helpers ─────────────────────────────────────────

interface FsEntry {
  isFile: boolean
  isDirectory: boolean
  file?: (cb: (f: File) => void, err?: (e: unknown) => void) => void
  createReader?: () => { readEntries: (cb: (es: FsEntry[]) => void, err?: (e: unknown) => void) => void }
}

async function walkEntry(entry: FsEntry, out: File[]): Promise<void> {
  if (entry.isFile && entry.file) {
    return new Promise<void>((resolve) => {
      entry.file!((f) => { out.push(f); resolve() }, () => resolve())
    })
  }
  if (entry.isDirectory && entry.createReader) {
    const reader = entry.createReader()
    return new Promise<void>((resolve) => {
      const collected: FsEntry[] = []
      function readBatch() {
        reader.readEntries(async (entries) => {
          if (entries.length === 0) {
            await Promise.all(collected.map(e => walkEntry(e, out)))
            resolve()
          } else {
            collected.push(...entries)
            readBatch()
          }
        }, () => resolve())
      }
      readBatch()
    })
  }
}
