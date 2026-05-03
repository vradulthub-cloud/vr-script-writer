/**
 * upload-storage.ts — IndexedDB persistence so an in-flight 3 GB upload
 * survives a browser reload.
 *
 * One row per (file fingerprint + key). Fingerprint = name|size|lastModified —
 * matches what we'd hash for idempotency and is stable enough that re-dropping
 * the same file resumes the existing upload rather than starting over.
 */

const DB_NAME = "eclatech-uploads"
const DB_VERSION = 1
const STORE = "active"

export type UploadState = {
  /** primaryKey: `${fingerprint}|${key}` */
  id: string
  fingerprint: string
  studio: string
  key: string
  upload_id: string
  size: number
  part_size: number
  part_count: number
  /** ETags collected so far, indexed by part_number (1..N). Sparse array. */
  parts: Array<{ part_number: number; etag: string }>
  created_at: number
  updated_at: number
}

export function fingerprint(file: File): string {
  return `${file.name}|${file.size}|${file.lastModified}`
}

function isAvailable(): boolean {
  return typeof indexedDB !== "undefined"
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!isAvailable()) {
      reject(new Error("IndexedDB not available"))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" })
        store.createIndex("fingerprint", "fingerprint", { unique: false })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => Promise<T> | T): Promise<T> {
  const db = await openDb()
  return new Promise<T>((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const store = t.objectStore(STORE)
    let result: T
    Promise.resolve(fn(store))
      .then((r) => { result = r })
      .catch(reject)
    t.oncomplete = () => resolve(result)
    t.onerror = () => reject(t.error)
    t.onabort = () => reject(t.error || new Error("tx aborted"))
  })
}

function reqPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function save(state: UploadState): Promise<void> {
  if (!isAvailable()) return
  state.updated_at = Date.now()
  await tx("readwrite", (store) => reqPromise(store.put(state)))
}

export async function load(id: string): Promise<UploadState | null> {
  if (!isAvailable()) return null
  return tx("readonly", async (store) => {
    const r = await reqPromise(store.get(id))
    return (r ?? null) as UploadState | null
  })
}

export async function loadByFingerprint(fp: string): Promise<UploadState[]> {
  if (!isAvailable()) return []
  return tx("readonly", async (store) => {
    const ix = store.index("fingerprint")
    const r = await reqPromise(ix.getAll(fp))
    return (r ?? []) as UploadState[]
  })
}

export async function remove(id: string): Promise<void> {
  if (!isAvailable()) return
  await tx("readwrite", (store) => reqPromise(store.delete(id)))
}

export async function listAll(): Promise<UploadState[]> {
  if (!isAvailable()) return []
  return tx("readonly", async (store) => {
    const r = await reqPromise(store.getAll())
    return (r ?? []) as UploadState[]
  })
}

/** Drop entries older than ``maxAgeMs`` — rough housekeeping for orphaned
 *  uploads the user never resumed. Default 7 days. */
export async function pruneOld(maxAgeMs = 7 * 24 * 60 * 60 * 1000): Promise<number> {
  if (!isAvailable()) return 0
  const cutoff = Date.now() - maxAgeMs
  return tx("readwrite", async (store) => {
    const all = (await reqPromise(store.getAll())) as UploadState[]
    let removed = 0
    for (const s of all) {
      if (s.updated_at < cutoff) {
        await reqPromise(store.delete(s.id))
        removed += 1
      }
    }
    return removed
  })
}
