/**
 * upload-multipart.ts — orchestrator for a single browser → MEGA S4 upload.
 *
 * Hot path (per file):
 *   1. POST /api/uploads/multipart/init   → upload_id, part_size, part_count
 *   2. POST /api/uploads/multipart/sign-parts (in batches) → presigned PUT URLs
 *   3. PUT each chunk to S4 (4 in flight) → capture ETag from response header
 *   4. POST /api/uploads/multipart/complete → final ETag + presigned GET URL
 *
 * On failure mid-upload: POST /api/uploads/multipart/abort, then retry from
 * scratch with a fresh upload_id.
 *
 * Persists progress to IndexedDB on every part-success so a reload + re-drop
 * of the same file resumes where it left off rather than starting over.
 */
import { api, type UploadInitResponse, type PartUrl } from "@/lib/api"
import { fingerprint, load, save, remove, type UploadState } from "@/lib/upload-storage"

export type UploadProgress = {
  /** Upload phase. */
  phase: "init" | "uploading" | "completing" | "done" | "error" | "aborted"
  /** Bytes successfully uploaded so far. */
  bytesUploaded: number
  /** File total in bytes. */
  bytesTotal: number
  /** Part numbers that have completed. */
  partsCompleted: number
  partsTotal: number
  /** Last error message, if any. */
  error?: string
  /** Final S4 key once the upload completes. */
  key?: string
  /** Presigned GET link returned by the complete endpoint. */
  presignedUrl?: string
}

export type StartArgs = {
  file: File
  studio: string
  scene_id: string
  subfolder: string
  filename: string
  /** Auth token threaded through to the api() factory. */
  idToken: string
  /** Concurrent part PUTs in flight. Default 4. */
  concurrency?: number
  /** Progress callback — fires on every state transition + every part success. */
  onProgress?: (p: UploadProgress) => void
  /** AbortSignal — tearing down the dashboard or hitting [×] cancels in-flight PUTs. */
  signal?: AbortSignal
}

export type StartResult = {
  ok: boolean
  key?: string
  presignedUrl?: string
  error?: string
}

const SIGN_BATCH = 50  // sign up to 50 part URLs in one round-trip

/** Public entry point. Returns when the upload completes, fails, or aborts. */
export async function uploadFile(args: StartArgs): Promise<StartResult> {
  const { file, idToken, onProgress, signal } = args
  const concurrency = Math.max(1, args.concurrency ?? 4)
  const client = api(idToken)
  const fp = fingerprint(file)

  let state: UploadState | null = null
  let init: UploadInitResponse

  // Try resume — same fingerprint + same destination key.
  const desiredKey = buildDestinationKey(args)
  const resumeId = `${fp}|${desiredKey}`
  const resumed = await load(resumeId)
  if (resumed && resumed.key === desiredKey && resumed.size === file.size) {
    state = resumed
    init = {
      upload_id: resumed.upload_id,
      bucket: "",  // not needed for resume
      key: resumed.key,
      part_size: resumed.part_size,
      part_count: resumed.part_count,
    }
    onProgress?.({
      phase: "uploading",
      bytesUploaded: state.parts.length * state.part_size,
      bytesTotal: file.size,
      partsCompleted: state.parts.length,
      partsTotal: state.part_count,
    })
  } else {
    onProgress?.({ phase: "init", bytesUploaded: 0, bytesTotal: file.size, partsCompleted: 0, partsTotal: 0 })
    try {
      init = await client.uploads.initMultipart({
        studio:       args.studio,
        scene_id:     args.scene_id,
        subfolder:    args.subfolder,
        filename:     args.filename,
        size:         file.size,
        content_type: file.type || undefined,
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      onProgress?.({ phase: "error", bytesUploaded: 0, bytesTotal: file.size, partsCompleted: 0, partsTotal: 0, error: msg })
      return { ok: false, error: msg }
    }
    state = {
      id:         resumeId,
      fingerprint: fp,
      studio:     args.studio,
      key:        init.key,
      upload_id:  init.upload_id,
      size:       file.size,
      part_size:  init.part_size,
      part_count: init.part_count,
      parts:      [],
      created_at: Date.now(),
      updated_at: Date.now(),
    }
    await save(state)
  }

  // Determine which parts still need to be uploaded.
  const completed = new Set(state.parts.map(p => p.part_number))
  const todo: number[] = []
  for (let i = 1; i <= state.part_count; i++) {
    if (!completed.has(i)) todo.push(i)
  }

  // ── Sign batches lazily as the queue drains. ─────────────────────────────
  const partUrls = new Map<number, string>()
  async function ensureSigned(parts: number[]): Promise<void> {
    const missing = parts.filter(p => !partUrls.has(p))
    if (missing.length === 0) return
    const resp = await client.uploads.signParts({
      studio:      args.studio,
      key:         state!.key,
      upload_id:   state!.upload_id,
      part_numbers: missing,
    })
    for (const u of resp.urls as PartUrl[]) partUrls.set(u.part_number, u.url)
  }

  // Pre-sign the first chunk-batch.
  await ensureSigned(todo.slice(0, SIGN_BATCH))

  // ── Worker loop ──────────────────────────────────────────────────────────
  let nextIdx = 0
  let inFlight = 0
  let failed: Error | null = null
  let aborted = false

  const partETag = new Map<number, string>()
  for (const p of state.parts) partETag.set(p.part_number, p.etag)

  function emit() {
    const partsCompleted = partETag.size
    const bytesUploaded = Math.min(file.size, partsCompleted * state!.part_size)
    onProgress?.({
      phase: aborted ? "aborted" : (failed ? "error" : "uploading"),
      bytesUploaded,
      bytesTotal: file.size,
      partsCompleted,
      partsTotal: state!.part_count,
      error: failed?.message,
    })
  }

  async function uploadOnePart(partNumber: number): Promise<void> {
    const start = (partNumber - 1) * state!.part_size
    const end = Math.min(start + state!.part_size, file.size)
    const blob = file.slice(start, end)
    let attempts = 0
    while (true) {
      attempts++
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError")
      let url = partUrls.get(partNumber)
      if (!url) {
        await ensureSigned([partNumber])
        url = partUrls.get(partNumber)
      }
      if (!url) throw new Error(`No presigned URL for part ${partNumber}`)
      const res = await fetch(url, { method: "PUT", body: blob, signal })
      if (res.ok) {
        // ETag comes back quoted by S3; strip quotes for the complete payload.
        const raw = res.headers.get("ETag") ?? res.headers.get("etag") ?? ""
        const etag = raw.replace(/^"|"$/g, "")
        partETag.set(partNumber, etag)
        state!.parts.push({ part_number: partNumber, etag })
        await save(state!)
        emit()
        return
      }
      if (res.status === 403 || res.status === 401) {
        // URL likely expired — drop & re-sign on next attempt.
        partUrls.delete(partNumber)
      }
      if (attempts >= 4) {
        throw new Error(`Part ${partNumber} failed after ${attempts} attempts (HTTP ${res.status})`)
      }
      // Exponential backoff: 500ms / 1s / 2s
      await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempts - 1)))
    }
  }

  await new Promise<void>((resolve) => {
    function pump() {
      if (failed || aborted) {
        if (inFlight === 0) resolve()
        return
      }
      while (inFlight < concurrency && nextIdx < todo.length) {
        const partNumber = todo[nextIdx++]
        inFlight++
        uploadOnePart(partNumber)
          .then(() => {
            inFlight--
            // Pre-sign the next batch when we're 80% through the current one.
            if (nextIdx + concurrency >= partUrls.size) {
              ensureSigned(todo.slice(nextIdx, nextIdx + SIGN_BATCH)).catch(() => {})
            }
            pump()
          })
          .catch((err: Error) => {
            inFlight--
            if (signal?.aborted) {
              aborted = true
            } else {
              failed = err
            }
            pump()
          })
      }
      if (inFlight === 0 && nextIdx >= todo.length) resolve()
    }
    pump()
  })

  if (aborted) {
    try {
      await client.uploads.abort({ studio: args.studio, key: state.key, upload_id: state.upload_id })
    } catch { /* ignore */ }
    await remove(state.id)
    onProgress?.({ phase: "aborted", bytesUploaded: 0, bytesTotal: file.size, partsCompleted: partETag.size, partsTotal: state.part_count })
    return { ok: false, error: "aborted" }
  }
  if (failed) {
    try {
      await client.uploads.abort({ studio: args.studio, key: state.key, upload_id: state.upload_id })
    } catch { /* ignore */ }
    await remove(state.id)
    const msg = (failed as Error).message
    onProgress?.({ phase: "error", bytesUploaded: 0, bytesTotal: file.size, partsCompleted: partETag.size, partsTotal: state.part_count, error: msg })
    return { ok: false, error: msg }
  }

  onProgress?.({
    phase: "completing",
    bytesUploaded: file.size,
    bytesTotal: file.size,
    partsCompleted: state.part_count,
    partsTotal: state.part_count,
  })

  try {
    const resp = await client.uploads.complete({
      studio:    args.studio,
      key:       state.key,
      upload_id: state.upload_id,
      parts:     [...partETag.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([n, etag]) => ({ part_number: n, etag })),
      size:      file.size,
      subfolder: args.subfolder,
    })
    await remove(state.id)
    onProgress?.({
      phase: "done",
      bytesUploaded: file.size,
      bytesTotal: file.size,
      partsCompleted: state.part_count,
      partsTotal: state.part_count,
      key: resp.key,
      presignedUrl: resp.presigned_url,
    })
    return { ok: true, key: resp.key, presignedUrl: resp.presigned_url }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    onProgress?.({ phase: "error", bytesUploaded: file.size, bytesTotal: file.size, partsCompleted: state.part_count, partsTotal: state.part_count, error: msg })
    return { ok: false, error: msg }
  }
}

function buildDestinationKey(args: { scene_id: string; subfolder: string; filename: string }): string {
  return `${args.scene_id}/${args.subfolder}/${args.filename}`
}
