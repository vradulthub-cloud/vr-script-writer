/**
 * upload-classifier.ts — pure-function file → S4 destination resolver.
 *
 * Mirrors s4_client.normalize_scene_id and _STUDIO_ALIASES exactly so the
 * browser-side classification is consistent with what the FastAPI side
 * accepts. Don't loosen the regex without updating the Python side too.
 */

export type StudioCode = "FPVR" | "VRH" | "VRA" | "NJOI"

export type Subfolder =
  | "Description"
  | "Videos"
  | "Photos"
  | "Storyboard"
  | "Video Thumbnail"
  | "Legal"

export type RoutingDecision = {
  studio: StudioCode | null
  scene_id: string | null
  subfolder: Subfolder | null
  filename: string
  /** 0..1. 1.0 = ready for one-click upload. <1 = UI prompts for review. */
  confidence: number
  /** Short English explanation of how this file got routed (or didn't). */
  reason: string
}

/** Codebase-wide alias map: anything we might see in input → canonical code. */
export const STUDIO_ALIASES: Record<string, StudioCode> = {
  FPVR: "FPVR", VRH: "VRH", VRA: "VRA", NJOI: "NJOI",
  fpvr: "FPVR", vrh: "VRH", vra: "VRA", njoi: "NJOI",
  NNJOI: "NJOI", nnjoi: "NJOI",
  FuckPassVR: "FPVR", FuckpassVR: "FPVR", fuckpassvr: "FPVR",
  VRHush: "VRH", vrhush: "VRH",
  VRAllure: "VRA", vrallure: "VRA",
  NaughtyJOI: "NJOI", naughtyjoi: "NJOI",
}

/** Bucket name for each canonical studio. */
export const STUDIO_BUCKETS: Record<StudioCode, string> = {
  FPVR: "fpvr",
  VRH:  "vrh",
  VRA:  "vra",
  NJOI: "njoi",
}

/** Mirrors s4_client.normalize_scene_id. Throws on bad input. */
export function normalizeSceneId(raw: string): string {
  const m = raw.trim().match(/^([A-Za-z]+)0*(\d+)$/)
  if (!m) throw new Error(`Not a scene ID: ${raw}`)
  return `${m[1].toUpperCase()}${String(parseInt(m[2], 10)).padStart(4, "0")}`
}

/** Resolve any alias to canonical studio code, or null if unrecognized. */
export function resolveStudio(raw: string): StudioCode | null {
  if (!raw) return null
  const upper = raw.toUpperCase()
  return (
    STUDIO_ALIASES[raw] ??
    STUDIO_ALIASES[upper] ??
    (upper in STUDIO_BUCKETS ? (upper as StudioCode) : null)
  )
}

const SCENE_ID_RE = /\b(FPVR|VRH|VRA|NJOI|NNJOI)\s*0*(\d{1,4})\b/i
const LEGAL_HINT_RE = /\b(2257|w-?9|id[_-]?front|id[_-]?back|passport|license|release[_-]?form)\b/i
const THUMBNAIL_HINT_RE = /\bthumb(?:nail)?\b/i
const PHOTOS_NUMBERED_RE = /(?:photos[_-]?\d{1,4}|_\d{3,})/i

const VIDEO_EXTS = new Set([".mp4", ".mov", ".mkv", ".m4v"])
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif"])
const DESC_EXTS = new Set([".docx", ".doc", ".txt", ".rtf"])
const ZIP_EXTS = new Set([".zip"])
const PDF_EXTS = new Set([".pdf"])

function ext(filename: string): string {
  const i = filename.lastIndexOf(".")
  return i < 0 ? "" : filename.slice(i).toLowerCase()
}

function classifySubfolder(filename: string): {
  subfolder: Subfolder | null
  confidence: number
  reason: string
} {
  const e = ext(filename)
  const base = filename.toLowerCase()

  // Legal beats everything — explicit form / ID hints route to Legal regardless of ext.
  if (LEGAL_HINT_RE.test(base)) {
    return { subfolder: "Legal", confidence: 0.95, reason: "Filename matches legal/ID pattern" }
  }
  if (PDF_EXTS.has(e)) {
    return { subfolder: "Legal", confidence: 0.85, reason: "PDF defaults to Legal (release/2257)" }
  }
  if (DESC_EXTS.has(e)) {
    return { subfolder: "Description", confidence: 1, reason: `${e} → Description` }
  }
  if (VIDEO_EXTS.has(e)) {
    return { subfolder: "Videos", confidence: 1, reason: `${e} → Videos` }
  }
  if (ZIP_EXTS.has(e)) {
    return { subfolder: "Photos", confidence: 1, reason: ".zip photoset → Photos" }
  }
  if (IMAGE_EXTS.has(e)) {
    if (THUMBNAIL_HINT_RE.test(base)) {
      return { subfolder: "Video Thumbnail", confidence: 0.9, reason: "Image with 'thumb' hint" }
    }
    if (PHOTOS_NUMBERED_RE.test(base)) {
      return { subfolder: "Storyboard", confidence: 0.9, reason: "Numbered Photos_NNN pattern" }
    }
    // Plain image, no hint — default to Storyboard but flag for review.
    return { subfolder: "Storyboard", confidence: 0.5, reason: "Image without clear hint — pick Storyboard or Video Thumbnail" }
  }
  return { subfolder: null, confidence: 0, reason: "Unrecognized extension" }
}

function classifyScene(filename: string): {
  studio: StudioCode | null
  scene_id: string | null
  reason: string
} {
  const m = filename.match(SCENE_ID_RE)
  if (!m) return { studio: null, scene_id: null, reason: "No scene ID in filename" }
  const prefix = m[1].toUpperCase()
  const studio = resolveStudio(prefix)
  if (!studio) return { studio: null, scene_id: null, reason: `Unknown studio prefix: ${prefix}` }
  const num = parseInt(m[2], 10)
  return {
    studio,
    scene_id: `${studio}${String(num).padStart(4, "0")}`,
    reason: `Matched ${studio}${String(num).padStart(4, "0")} in filename`,
  }
}

/**
 * Classify a single file. Returns a routing decision; the UI surfaces any
 * sub-1.0 confidence and lets the user override before commit.
 */
export function classify(file: File): RoutingDecision {
  const filename = file.name
  const sceneInfo = classifyScene(filename)
  const subInfo = classifySubfolder(filename)

  // No scene — block until user picks one. Subfolder hint stands.
  if (!sceneInfo.scene_id || !sceneInfo.studio) {
    return {
      studio: null,
      scene_id: null,
      subfolder: subInfo.subfolder,
      filename,
      confidence: 0,
      reason: sceneInfo.reason,
    }
  }
  // Scene found. Confidence = subfolder confidence; reason combines.
  return {
    studio: sceneInfo.studio,
    scene_id: sceneInfo.scene_id,
    subfolder: subInfo.subfolder,
    filename,
    confidence: subInfo.confidence,
    reason: `${sceneInfo.reason}; ${subInfo.reason}`,
  }
}

/** Build the canonical S4 key from a fully-resolved decision. */
export function buildKey(d: {
  scene_id: string
  subfolder: Subfolder
  filename: string
}): string {
  return `${normalizeSceneId(d.scene_id)}/${d.subfolder}/${d.filename}`
}

export const SUBFOLDERS: Subfolder[] = [
  "Description",
  "Videos",
  "Photos",
  "Storyboard",
  "Video Thumbnail",
  "Legal",
]

/** Format bytes as a short human-readable string ("2.8 GB"). */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(0)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`
  const gb = mb / 1024
  return `${gb.toFixed(gb < 10 ? 2 : 1)} GB`
}
