/**
 * API client for the FastAPI backend (port 8502).
 *
 * All requests attach the Google ID token from the next-auth session as
 * a Bearer token — the FastAPI auth middleware validates it with Google.
 *
 * Usage (server component):
 *   import { api } from "@/lib/api"
 *   import { auth } from "@/auth"
 *   const session = await auth()
 *   const tickets = await api(session).tickets.list()
 *
 * Usage (client component):
 *   import { useApi } from "@/lib/api"
 *   const { data } = useApi("/tickets/")
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8502"

export const API_BASE_URL = API_BASE

/**
 * Build a thumbnail URL for a scene. In dev-mock mode the endpoint doesn't
 * exist, so we point at picsum.photos with a seed for deterministic but varied
 * placeholder images. Production path goes straight to the MEGA proxy.
 */
export function thumbnailUrl(sceneId: string): string {
  if (
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_DEV_AUTH_MOCK === "1"
  ) {
    return `https://picsum.photos/seed/${encodeURIComponent(sceneId)}/320/180`
  }
  return `${API_BASE}/api/scenes/${encodeURIComponent(sceneId)}/thumbnail`
}

// ─── Low-level fetch ────────────────────────────────────────────────────────

// Dev-only guard: dead-code-eliminated in production because Next.js inlines
// NODE_ENV. See lib/dev-fixtures.ts for the mock payloads.
const DEV_MOCK =
  process.env.NODE_ENV !== "production" &&
  (process.env.NEXT_PUBLIC_DEV_AUTH_MOCK === "1" ||
    process.env.DEV_AUTH_MOCK === "1")

interface FetchOptions extends RequestInit {
  /**
   * Set to true when the caller expects a 204 No Content response.
   * If false (the default) and the server returns 204, apiFetch throws
   * rather than silently returning `undefined as T` — that silent cast
   * causes callers that destructure the result to crash far from the
   * source of the bug.
   */
  expectEmpty?: boolean
}

const DEFAULT_TIMEOUT_MS = 30_000

async function apiFetch<T>(
  path: string,
  idToken: string | undefined,
  options: FetchOptions = {},
): Promise<T> {
  const { expectEmpty, signal: callerSignal, ...rest } = options

  if (DEV_MOCK) {
    const { mockApi } = await import("./dev-mock-api")
    return mockApi<T>(path, rest)
  }

  const url = `${API_BASE}/api${path}`
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string>),
  }
  if (idToken) {
    headers["Authorization"] = `Bearer ${idToken}`
  }

  // 30s timeout unless caller already wired an AbortSignal. A hung
  // backend used to freeze the UI indefinitely.
  const controller = callerSignal ? undefined : new AbortController()
  const timeoutId = controller
    ? setTimeout(() => controller.abort(new DOMException("Timeout", "TimeoutError")), DEFAULT_TIMEOUT_MS)
    : undefined
  const signal = callerSignal ?? controller?.signal

  let res: Response
  try {
    res = await fetch(url, { ...rest, headers, signal })
  } catch (err) {
    if (err instanceof DOMException && (err.name === "TimeoutError" || err.name === "AbortError")) {
      throw new ApiError(0, `Request timed out after ${DEFAULT_TIMEOUT_MS / 1000}s: ${path}`)
    }
    throw new ApiError(0, err instanceof Error ? err.message : "Network error")
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId)
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new ApiError(res.status, body)
  }

  if (res.status === 204) {
    if (expectEmpty) return undefined as T
    throw new ApiError(
      204,
      `Unexpected 204 from ${path} — caller expected a response body. Use postVoid/patchVoid for endpoints that return No Content.`,
    )
  }

  return res.json() as Promise<T>
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`API ${status}: ${body}`)
    this.name = "ApiError"
  }
}

// ─── Types ──────────────────────────────────────────────────────────────────

export interface Ticket {
  ticket_id: string
  title: string
  description: string
  project: string
  type: string
  priority: string
  status: string
  submitted_by: string
  submitted_at: string
  assignee: string
  notes: string
  resolved_at: string
  linked_items: string
}

export interface TicketCreate {
  title: string
  description?: string
  project?: string
  type?: string
  priority?: string
  linked_items?: string
  /** Optional initial status — defaults server-side to "New". */
  status?: string
  /** Optional assignee name at create time. */
  assignee?: string
  /** Additional names to notify beyond the admin list. */
  notify?: string[]
}

export interface TicketUpdate {
  status?: string
  assignee?: string
  priority?: string
  note?: string
}

export type TicketStats = Record<string, number>

export interface SyncStatus {
  source: string
  last_synced_at: string
  row_count: number
  status: string
  error: string
}

export interface Scene {
  id: string
  studio: string
  grail_tab: string
  site_code: string
  title: string
  performers: string
  categories: string
  tags: string
  release_date: string
  female: string
  male: string
  plot: string
  theme: string
  is_compilation: boolean
  has_description: boolean
  has_videos: boolean
  video_count: number
  has_thumbnail: boolean
  has_photos: boolean
  has_storyboard: boolean
  storyboard_count: number
  mega_path: string
  grail_row: number
}

export interface NamingIssue {
  type: string
  file: string
  issue: string
}

export interface SceneStats {
  total: number
  by_studio: Record<string, number>
  complete: number
  missing_any: number
}

export interface Script {
  id: number
  tab_name: string
  sheet_row: number
  studio: string
  shoot_date: string
  female: string
  male: string
  theme: string
  plot: string
  title: string
  script_status: string
  // Additional fields returned when the row has been filled out past the
  // minimum — surface in the shoot modal so directors can see wardrobe at
  // a glance. Optional since they may be blank on fresh rows.
  wardrobe_f?: string
  wardrobe_m?: string
  shoot_location?: string
  props?: string
}

export interface Model {
  name: string
  agency: string
  agency_link: string
  rate: string
  rank: string            // Great / Good / Moderate / Poor
  notes: string           // Available For / acts
  info: string            // Raw "Age: 22 · Last booked: Mar 2026 · ..."
  age: string
  last_booked: string
  bookings_count: string
  location: string
  opportunity_score: number  // 0–100
  sheet_data: Record<string, string>  // all booking sheet columns
}

export interface TrendingModel {
  name: string
  photo_url: string
  platform: string       // "SLR" | "VRP"
  profile_url: string
  scenes: string
  followers: string
  views: string
}

export interface BookingHistory {
  total: number
  last_date: string
  last_display: string
  studios: Record<string, number>
}

export interface ShootScene {
  date_raw: string
  studio: string
  type: string
  female: string
  male: string
  agency: string
  male_agency: string
}

export interface ShootDate {
  date_key: string
  date_display: string
  scenes: ShootScene[]
}

export interface CallSheetResult {
  doc_id: string
  doc_url: string
  title: string
}

export interface ProfileScene {
  title: string
  date: string
  studio: string
  url: string
  thumb: string
  duration: string
  views: string
  likes: string
  comments: string
}

export interface ModelProfile {
  name: string
  photo_url: string
  bio: Record<string, string>
  identity_uncertain?: boolean
  slr_profile_url: string
  slr_scenes: ProfileScene[]
  vrp_profile_url: string
  vrp_scenes: ProfileScene[]
  booking_history: BookingHistory
  cached_at: string
}

export interface Approval {
  approval_id: string
  scene_id: string
  studio: string
  content_type: string
  submitted_by: string
  submitted_at: string
  status: string
  decided_by: string
  decided_at: string
  content_json: string
  notes: string
  target_sheet: string
  target_range: string
}

export interface UserProfile {
  email: string
  name: string
  role: string           // "admin" | "editor"
  allowed_tabs: string   // comma-separated or "ALL"
}

export interface UserUpdate {
  role?: string
  allowed_tabs?: string
}

// ── Shoot Board types ──────────────────────────────────────────────────
export interface ValidityCheck {
  check: string           // "naming" | "count" | "format"
  status: "pass" | "fail" | "warn"
  message: string
}

export type AssetType =
  | "script_done" | "call_sheet_sent" | "legal_run" | "grail_run"
  | "bg_edit_uploaded" | "solo_uploaded"
  | "title_done" | "encoded_uploaded"
  | "photoset_uploaded" | "storyboard_uploaded" | "legal_docs_uploaded"

export type AssetStatus = "not_present" | "available" | "validated" | "stuck"

export interface SceneAssetState {
  asset_type: AssetType
  status: AssetStatus
  first_seen_at: string
  validated_at: string
  last_checked_at: string
  validity: ValidityCheck[]
}

export interface BoardShootScene {
  scene_id: string
  studio: string
  scene_type: "BG" | "BGCP" | "Solo" | "JOI" | string
  grail_tab: string
  position: 1 | 2
  title: string
  performers: string
  has_thumbnail: boolean
  mega_path: string
  assets: SceneAssetState[]
}

export interface Shoot {
  shoot_id: string
  shoot_date: string
  female_talent: string
  female_agency: string
  male_talent: string
  male_agency: string
  destination: string
  location: string
  home_owner: string
  source_tab: string
  status: "active" | "cancelled" | string
  scenes: BoardShootScene[]
  aging_hours: number
  // Day-of billing info. Optional because the sheet populates these only
  // after the talent fills out their W9 in the morning — before that the
  // modal should render a placeholder ("Pending W9"). Backend syncs these
  // from the legal-paperwork pipeline; payment_name is whatever the
  // talent wrote on the W9 (their legal name for the 1099), which can
  // differ from their stage name.
  female_rate?: string
  female_payment_name?: string
  male_rate?: string
  male_payment_name?: string
}

export interface LegalDocFile {
  name: string
  web_view_link: string
  mime_type: string
}

export interface LegalDocsResult {
  folder_url: string | null
  folder_name: string | null
  files: LegalDocFile[]
  w9_name: string | null
}

// ─── Compliance ───────────────────────────────────────────────────────────────

export interface ComplianceShoot {
  shoot_id: string
  shoot_date: string
  female_talent: string
  male_talent: string
  drive_folder_url: string | null
  drive_folder_id: string | null
  drive_folder_name: string | null
  pdfs_ready: boolean
  photos_uploaded: number
  is_complete: boolean
  scene_id: string
  studio: string
}

export interface CompliancePrepareResult {
  folder_id: string
  folder_url: string
  folder_name: string
  female_pdf_id: string
  male_pdf_id: string
  male_known: boolean
  dates_filled: boolean
  message: string
}

export interface PhotoUploadResult {
  uploaded: string[]
  drive_file_ids: string[]
  mega_paths: string[]
  errors: string[]
}

export interface MegaSyncResult {
  status: string   // "ok" | "error"
  mega_path: string
  files_copied: number
  message: string
}

export interface FillFormRequest {
  talent: string          // "female" | male stage name e.g. "MikeMancini"
  legal_name: string
  stage_name?: string
  dob?: string            // YYYY-MM-DD
  place_of_birth?: string
  street_address?: string
  city_state_zip?: string
  phone?: string
  email?: string
  id1_type?: string
  id1_number?: string
  id2_type?: string
  id2_number?: string
  signature?: string
  company_name?: string
}

// ── New in-Hub signing flow (TKT-0150) ─────────────────────────────────────

export type TaxClassification =
  | "individual" | "c_corp" | "s_corp" | "partnership"
  | "trust_estate" | "llc" | "other"

export interface SignRequest {
  talent_role: "female" | "male"
  talent_slug: string
  talent_display: string

  // W-9 (page 1 of legacy template)
  legal_name: string
  business_name?: string
  tax_classification: TaxClassification
  llc_class?: string                     // 'C' | 'S' | 'P' (when tax_classification='llc')
  other_classification?: string
  exempt_payee_code?: string
  fatca_code?: string
  tin_type: "ssn" | "ein"
  tin: string                            // raw digits

  // 2257 Performer Names Disclosure
  dob: string                            // YYYY-MM-DD
  place_of_birth: string
  street_address: string
  city_state_zip: string
  phone: string
  email: string
  id1_type: string
  id1_number: string
  id2_type?: string
  id2_number?: string
  stage_names?: string
  professional_names?: string
  nicknames_aliases?: string
  previous_legal_names?: string

  // Signature image, base64 PNG
  signature_png: string                  // "data:image/png;base64,..."
}

export interface SignResult {
  shoot_id: string
  talent_role: string
  talent_slug: string
  signed_at: string
  pdf_local_path: string
  pdf_mega_path: string
  contract_version: string
}

export interface SignedSummary {
  talent_role: string
  talent_slug: string
  talent_display: string
  legal_name: string
  signed_at: string
  pdf_mega_path: string
}

/**
 * Server-persisted photo (TKT-0151). Photos saved here survive across visits
 * and don't depend on talent having signed paperwork yet — they live in the
 * compliance_photos table and on local disk, with an optional MEGA copy.
 */
export interface CompliancePhoto {
  slot_id: string
  talent_role: string
  label: string
  mime_type: string
  file_size: number
  uploaded_at: string
  mega_path: string
  url: string                 // GET endpoint that serves the bytes
}

export const SHOOT_ASSET_ORDER: readonly AssetType[] = [
  "script_done",
  "call_sheet_sent",
  "legal_run",
  "grail_run",
  "bg_edit_uploaded",
  "solo_uploaded",
  "title_done",
  "encoded_uploaded",
  "photoset_uploaded",
  "storyboard_uploaded",
  "legal_docs_uploaded",
] as const

export const SHOOT_ASSET_LABELS: Record<AssetType, string> = {
  script_done:          "Script",
  call_sheet_sent:      "Call sheet",
  legal_run:            "Legal run",
  grail_run:            "Grail run",
  bg_edit_uploaded:     "BG edit",
  solo_uploaded:        "Solo → Flo",
  title_done:           "Title",
  encoded_uploaded:     "Encoded",
  photoset_uploaded:    "Photoset",
  storyboard_uploaded:  "Storyboard",
  legal_docs_uploaded:  "Legal docs",
}

export interface Notification {
  notif_id: string
  timestamp: string
  recipient: string
  type: string           // ticket_created, ticket_status, approval_submitted, etc.
  title: string
  message: string
  read: number           // 0 or 1
  link: string
}

export interface TaskRow {
  task_id: string
  task_type: string
  status: string         // pending, running, completed, failed
  progress: number       // 0..1
  created_at: string
  started_at: string
  completed_at: string
  created_by: string
  error: string
}

export interface TaskStats {
  pending: number
  running: number
  completed: number
  failed: number
  total: number
}

export interface PromptEntry {
  key: string
  label: string
  group: string         // e.g. "Titles", "Descriptions", "Compilations", "Scripts"
  content: string       // active text — override if present, otherwise default
  default: string       // bundled default for diff/revert UI
  is_overridden: boolean
  updated_by: string
  updated_at: string
}

export interface CalendarEventRow {
  event_id: string
  date: string           // YYYY-MM-DD
  title: string
  kind: string
  color: string
  notes: string
  created_by: string
  created_at: string
}

export interface Treatment {
  name: string
  featured: boolean
}

export interface LocalTitleResult {
  data_url: string
  treatment_name: string
  error: string | null
}

export interface CompSceneRow {
  scene_id: string
  scene_num: number
  title: string
  performers: string
  slr_link: string
  mega_link: string
}

export interface ExistingComp {
  comp_id: string
  title: string
  volume: string
  status: string
  studio_key: string
  created: string
  created_by: string
  updated: string
  description: string
  notes: string
  scene_count: number
  scenes: CompSceneRow[]
}

// ─── API client factory ──────────────────────────────────────────────────────

/**
 * React cache() dedupes identical calls within a single server render tree.
 * Wrap idempotent GETs that multiple pages or layouts might issue in parallel
 * (e.g. users.me() is fetched by AppShell AND several page components).
 */
import { cache } from "react"

/**
 * Normalize role/allowed_tabs at the boundary so downstream comparisons
 * (role === "admin", allowedTabs.split(",")) behave predictably even if
 * the Google Sheet has "Admin" or leading/trailing whitespace.
 */
function normalizeProfile(p: UserProfile): UserProfile {
  return {
    ...p,
    role: (p.role ?? "").trim().toLowerCase(),
    allowed_tabs: (p.allowed_tabs ?? "").trim(),
  }
}

export const cachedUsersMe = cache(
  async (idToken: string | undefined): Promise<UserProfile> => {
    const raw = await apiFetch<UserProfile>("/users/me", idToken)
    return normalizeProfile(raw)
  },
)

export function api(idTokenOrSession: string | { idToken?: string } | null) {
  const token =
    typeof idTokenOrSession === "string"
      ? idTokenOrSession
      : (idTokenOrSession?.idToken ?? undefined)

  const get = <T>(path: string) => apiFetch<T>(path, token)
  const post = <T>(path: string, body: unknown) =>
    apiFetch<T>(path, token, { method: "POST", body: JSON.stringify(body) })
  const patch = <T>(path: string, body: unknown) =>
    apiFetch<T>(path, token, { method: "PATCH", body: JSON.stringify(body) })
  // For multipart/form-data (file uploads) — do NOT set Content-Type, let the browser set boundary
  const postForm = <T>(path: string, formData: FormData, signal?: AbortSignal) => {
    // Pass the FormData through in dev mock so route handlers can inspect
    // form fields (slot_id, label, etc.) — apiFetch ignores the body for
    // dev mock JSON shaping anyway, but our mock route reads it.
    if (DEV_MOCK) return apiFetch<T>(path, token, { method: "POST", body: formData as unknown as BodyInit })
    const url = `${API_BASE}/api${path}`
    const headers: Record<string, string> = {}
    if (token) headers["Authorization"] = `Bearer ${token}`
    return fetch(url, { method: "POST", headers, body: formData, signal }).then(r => {
      if (!r.ok) throw new ApiError(r.status, r.statusText)
      return r.json() as Promise<T>
    })
  }
  // For endpoints that legitimately return 204 No Content.
  const postVoid = (path: string, body: unknown) =>
    apiFetch<void>(path, token, { method: "POST", body: JSON.stringify(body), expectEmpty: true })
  const del = <T>(path: string) => apiFetch<T>(path, token, { method: "DELETE" })
  const delVoid = (path: string) =>
    apiFetch<void>(path, token, { method: "DELETE", expectEmpty: true })

  return {
    health: () => get<{ status: string; version: string; syncs: Record<string, unknown> }>("/health"),

    sync: {
      status: () => get<SyncStatus[]>("/sync/status"),
      trigger: () => post<{ status: string; results: Record<string, number | string> }>("/sync/trigger", {}),
    },

    tickets: {
      list: (filters?: {
        status?: string
        project?: string
        priority?: string
        assignee?: string
        type?: string
        limit?: number
      }) => {
        const params = new URLSearchParams()
        if (filters?.status)   params.set("status",   filters.status)
        if (filters?.project)  params.set("project",  filters.project)
        if (filters?.priority) params.set("priority", filters.priority)
        if (filters?.assignee) params.set("assignee", filters.assignee)
        if (filters?.type)     params.set("type",     filters.type)
        if (filters?.limit)    params.set("limit",    String(filters.limit))
        const qs = params.toString()
        return get<Ticket[]>(`/tickets/${qs ? `?${qs}` : ""}`)
      },
      stats: () => get<TicketStats>("/tickets/stats"),
      get: (id: string) => get<Ticket>(`/tickets/${encodeURIComponent(id)}`),
      create: (body: TicketCreate) => post<Ticket>("/tickets/", body),
      update: (id: string, body: TicketUpdate) => patch<Ticket>(`/tickets/${encodeURIComponent(id)}`, body),
      bulkUpdate: (body: {
        ticket_ids: string[]
        status?: string
        assignee?: string
        priority?: string
      }) =>
        post<{ updated: string[]; skipped: { ticket_id: string; reason: string }[] }>(
          "/tickets/bulk-update",
          body,
        ),
    },

    scenes: {
      list: (filters?: { studio?: string; missing_only?: boolean; missing_descriptions?: boolean; search?: string; page?: number; limit?: number }) => {
        const params = new URLSearchParams()
        if (filters?.studio) params.set("studio", filters.studio)
        if (filters?.missing_only) params.set("missing_only", "true")
        if (filters?.missing_descriptions) params.set("missing_descriptions", "true")
        if (filters?.search) params.set("search", filters.search)
        if (filters?.page) params.set("page", String(filters.page))
        if (filters?.limit) params.set("limit", String(filters.limit))
        const qs = params.toString()
        return get<Scene[]>(`/scenes/${qs ? `?${qs}` : ""}`)
      },
      stats: () => get<SceneStats>("/scenes/stats"),
      get: (id: string) => get<Scene>(`/scenes/${id}`),
      updateTitle: (id: string, value: string) =>
        patch<{ ok: boolean }>(`/scenes/${id}/title`, { value }),
      updateCategories: (id: string, value: string) =>
        patch<{ ok: boolean }>(`/scenes/${id}/categories`, { value }),
      updateTags: (id: string, value: string) =>
        patch<{ ok: boolean }>(`/scenes/${id}/tags`, { value }),
      generateTitle: (
        id: string,
        body: {
          female?: string
          male?: string
          theme?: string
          plot?: string
          wardrobe_f?: string
          wardrobe_m?: string
          location?: string
          props?: string
        },
      ) =>
        post<{ title: string }>(`/scenes/${id}/generate-title`, body),
      namingIssues: (id: string) =>
        get<{ scene_id: string; issues: NamingIssue[]; ok: boolean }>(`/scenes/${id}/naming-issues`),
      createFolder: (sceneId: string) =>
        post<{ status: string; scene_id: string }>("/scenes/create-folder", { scene_id: sceneId }),
    },

    scripts: {
      list: (filters?: { studio?: string; tab_name?: string; needs_script?: boolean; search?: string; limit?: number }) => {
        const params = new URLSearchParams()
        if (filters?.studio) params.set("studio", filters.studio)
        if (filters?.tab_name) params.set("tab_name", filters.tab_name)
        if (filters?.needs_script) params.set("needs_script", "true")
        if (filters?.search) params.set("search", filters.search)
        params.set("limit", String(filters?.limit ?? 500))
        const qs = params.toString()
        return get<Script[]>(`/scripts/${qs ? `?${qs}` : ""}`)
      },
      tabs: () => get<string[]>("/scripts/tabs"),
      save: (body: { script_id?: number; tab_name: string; sheet_row: number; theme: string; plot: string; wardrobe_f?: string; wardrobe_m?: string; shoot_location?: string; props?: string }) =>
        post<{ id: number; status: string }>("/scripts/save", body),
      validate: (body: { theme: string; plot: string; wardrobe_f: string; wardrobe_m?: string; shoot_location: string; female?: string; male?: string }) =>
        post<{ violations: string[]; passed: boolean }>("/scripts/validate", body),
      generateTitle: (body: {
        studio: string
        female?: string
        male?: string
        theme?: string
        plot?: string
        wardrobe_f?: string
        wardrobe_m?: string
        location?: string
        props?: string
      }) =>
        post<{ title: string }>("/scripts/title-generate", body),
    },

    descriptions: {
      save: (body: { scene_id: string; description: string; meta_title?: string; meta_description?: string }) =>
        post<{ ok: boolean }>("/descriptions/save", body),
      saveGrail: (body: { scene_id: string; description: string; meta_title?: string; meta_description?: string }) =>
        post<{ scene_id: string; status: string }>("/descriptions/save-grail", body),
      saveMega: (body: { scene_id: string; description: string; title?: string; meta_title?: string; meta_description?: string }) =>
        post<{ scene_id: string; mega_path: string; status: string }>("/descriptions/save-mega", body),
      seo: (body: { description: string; studio: string }) =>
        post<{ meta_title: string; meta_description: string }>("/descriptions/seo", body),
      regenerateParagraph: (body: {
        studio: string
        paragraph: string
        paragraph_index: number
        performer?: string
        title?: string
        plot?: string
        feedback?: string
      }) =>
        post<{ paragraph: string }>("/descriptions/regenerate-paragraph", body),
    },

    titles: {
      treatments: () => get<Treatment[]>("/titles/treatments"),
      local: (body: { text: string; treatments?: string[]; n?: number; seed?: number; auto_match?: boolean }) =>
        post<LocalTitleResult[]>("/titles/local", body),
      refine: (body: { text: string; treatment_name: string; refine_prompt: string; seed?: number }) =>
        post<LocalTitleResult>("/titles/refine", body),
      modelName: (body: { name: string; studio: string }) =>
        post<{ data_url: string; error?: string | null }>("/titles/model-name", body),
    },

    models: {
      list: (search?: string) => {
        const params = search ? `?search=${encodeURIComponent(search)}` : ""
        return get<Model[]>(`/models/${params}`)
      },
      get: (name: string) => get<Model>(`/models/${encodeURIComponent(name)}`),
      trending: (n = 10, refresh = false) => {
        const params = new URLSearchParams({ n: String(n) })
        if (refresh) params.set("refresh", "true")
        return get<TrendingModel[]>(`/models/trending?${params}`)
      },
      profile: (name: string, refresh = false) => {
        const params = refresh ? "?refresh=true" : ""
        return get<ModelProfile>(`/models/${encodeURIComponent(name)}/profile${params}`)
      },
      brief: (name: string, context: Record<string, string>) =>
        post<{ brief: string }>(`/models/${encodeURIComponent(name)}/brief`, { context }),
      clearCache: (name: string) =>
        del<{ ok: boolean }>(`/models/${encodeURIComponent(name)}/profile-cache`),
    },

    approvals: {
      list: (status?: string) => {
        const params = status ? `?status=${status}` : ""
        return get<Approval[]>(`/approvals/${params}`)
      },
      get: (id: string) => get<Approval>(`/approvals/${id}`),
      create: (body: { scene_id: string; studio: string; content_type: string; content_json: string; notes?: string; target_sheet?: string; target_range?: string }) =>
        post<Approval>("/approvals/", body),
      decide: (id: string, body: { decision: string; notes?: string }) =>
        patch<Approval>(`/approvals/${id}`, body),
    },

    callSheets: {
      tabs: () => get<string[]>("/call-sheets/tabs"),
      dates: (tab?: string) => {
        const params = tab ? `?tab=${encodeURIComponent(tab)}` : ""
        return get<ShootDate[]>(`/call-sheets/dates${params}`)
      },
      generate: (body: { date_key: string; door_code?: string; tab_name?: string }) =>
        post<CallSheetResult>("/call-sheets/generate", body),
    },

    compilations: {
      scenes: (studio?: string) => {
        const params = studio ? `?studio=${encodeURIComponent(studio)}` : ""
        return get<Scene[]>(`/compilations/scenes${params}`)
      },
      save: (body: { studio: string; title: string; scene_ids: string[]; description?: string; notes?: string; status?: string; volume?: string }) =>
        post<{ task_id: string; status: string }>("/compilations/save", body),
      existing: (studio?: string) => {
        const params = studio ? `?studio=${encodeURIComponent(studio)}` : ""
        return get<ExistingComp[]>(`/compilations/existing${params}`)
      },
      grailWrite: (body: { studio: string; title: string; scene_ids: string[] }) =>
        post<{ status: string; scene_count: number }>("/compilations/grail-write", body),
      patch: (
        compId: string,
        body: {
          title?: string
          volume?: string
          status?: string
          description?: string
          if_match?: { title: string; volume?: string; status?: string; description?: string }
        },
      ) =>
        patch<{
          status: string
          comp_id: string
          title: string
          volume: string
          comp_status: string
          description: string
        }>(`/compilations/${encodeURIComponent(compId)}`, body),
    },

    users: {
      me: async () => normalizeProfile(await get<UserProfile>("/users/me")),
      list: async () => (await get<UserProfile[]>("/users/")).map(normalizeProfile),
      update: async (email: string, body: UserUpdate) =>
        normalizeProfile(await patch<UserProfile>(`/users/${encodeURIComponent(email)}`, body)),
      create: async (body: { email: string; name: string; role?: string; allowed_tabs?: string }) =>
        normalizeProfile(await post<UserProfile>("/users/", body)),
      remove: (email: string) =>
        delVoid(`/users/${encodeURIComponent(email)}`),
    },

    syncOne: (source: string) =>
      post<{ source: string; row_count: number; status: string }>(`/sync/trigger/${encodeURIComponent(source)}`, {}),

    prompts: {
      list: () => get<PromptEntry[]>("/prompts/"),
      get: (key: string) => get<PromptEntry>(`/prompts/${encodeURIComponent(key)}`),
      save: (key: string, content: string) =>
        apiFetch<PromptEntry>(`/prompts/${encodeURIComponent(key)}`, token, {
          method: "PUT",
          body: JSON.stringify({ content }),
        }),
      revert: (key: string) => delVoid(`/prompts/${encodeURIComponent(key)}`),
    },

    tasks: {
      list: (filters?: { status?: string; limit?: number }) => {
        const params = new URLSearchParams()
        if (filters?.status) params.set("status", filters.status)
        if (filters?.limit) params.set("limit", String(filters.limit))
        const qs = params.toString()
        return get<TaskRow[]>(`/tasks/${qs ? `?${qs}` : ""}`)
      },
      stats: () => get<TaskStats>("/tasks/stats"),
    },

    notifications: {
      list: (limit = 50) => get<Notification[]>(`/notifications/?limit=${limit}`),
      unreadCount: () => get<{ count: number }>("/notifications/unread-count"),
      markRead: () => post<{ updated: number }>("/notifications/mark-read", {}),
      test: () => post<{ notif_id: string; recipient: string }>("/notifications/test", {}),
    },

    calendarEvents: {
      list: (range?: { from?: string; to?: string }) => {
        const params = new URLSearchParams()
        if (range?.from) params.set("from", range.from)
        if (range?.to) params.set("to", range.to)
        const qs = params.toString()
        return get<CalendarEventRow[]>(`/calendar-events/${qs ? `?${qs}` : ""}`)
      },
      create: (body: { date: string; title: string; kind?: string; color?: string; notes?: string }) =>
        post<CalendarEventRow>("/calendar-events/", body),
      remove: (eventId: string) =>
        delVoid(`/calendar-events/${encodeURIComponent(eventId)}`),
    },

    shoots: {
      list: (filters?: {
        from_date?: string
        to_date?: string
        studio?: string
        include_cancelled?: boolean
      }) => {
        const params = new URLSearchParams()
        if (filters?.from_date) params.set("from_date", filters.from_date)
        if (filters?.to_date) params.set("to_date", filters.to_date)
        if (filters?.studio) params.set("studio", filters.studio)
        if (filters?.include_cancelled) params.set("include_cancelled", "true")
        const qs = params.toString()
        return get<Shoot[]>(`/shoots/${qs ? `?${qs}` : ""}`)
      },
      get: (id: string) => get<Shoot>(`/shoots/${encodeURIComponent(id)}`),
      revalidate: (shootId: string, position: number, assetType: AssetType) =>
        post<SceneAssetState>(
          `/shoots/${encodeURIComponent(shootId)}/scenes/${position}/assets/${encodeURIComponent(assetType)}/revalidate`,
          {},
        ),
      legalDocs: (shootId: string) =>
        get<LegalDocsResult>(`/shoots/${encodeURIComponent(shootId)}/legal-docs`),
    },

    compliance: {
      shoots: (date?: string) => {
        const qs = date ? `?date=${encodeURIComponent(date)}` : ""
        return get<ComplianceShoot[]>(`/compliance/shoots${qs}`)
      },
      prepare: (shootId: string) =>
        post<CompliancePrepareResult>(`/compliance/shoots/${encodeURIComponent(shootId)}/prepare`, {}),
      fillForm: (shootId: string, req: FillFormRequest) =>
        post<CompliancePrepareResult>(`/compliance/shoots/${encodeURIComponent(shootId)}/fill-form`, req),
      /** Upload one file at a time; call in parallel for speed. */
      uploadPhoto: (
        shootId: string,
        file: File,
        label: string,
        signal?: AbortSignal,
      ) => {
        const fd = new FormData()
        fd.append("files", file, label)
        fd.append("labels", label)
        return postForm<PhotoUploadResult>(
          `/compliance/shoots/${encodeURIComponent(shootId)}/photos`,
          fd,
          signal,
        )
      },

      megaSync: (shootId: string, sceneId: string, studio: string) => {
        const fd = new FormData()
        fd.append("scene_id", sceneId)
        fd.append("studio", studio)
        return postForm<MegaSyncResult>(
          `/compliance/shoots/${encodeURIComponent(shootId)}/mega-sync`,
          fd,
        )
      },

      sign: (shootId: string, req: SignRequest) =>
        post<SignResult>(`/compliance/shoots/${encodeURIComponent(shootId)}/sign`, req),

      signed: (shootId: string) =>
        get<SignedSummary[]>(`/compliance/shoots/${encodeURIComponent(shootId)}/signed`),

      // ─── Server-persisted photos (TKT-0151) ──────────────────────────────
      // Photos saved here are independent of signing and the legacy Drive
      // folder. They reappear on the next visit and push to MEGA when the
      // shoot has a scene_id.
      listPhotos: (shootId: string) =>
        get<CompliancePhoto[]>(`/compliance/shoots/${encodeURIComponent(shootId)}/photos-v2`),

      uploadPhotoV2: (
        shootId: string,
        file: File,
        slotId: string,
        label: string,
        talentRole: string,
        signal?: AbortSignal,
      ) => {
        const fd = new FormData()
        fd.append("file", file, label)
        fd.append("slot_id", slotId)
        fd.append("label", label)
        fd.append("talent_role", talentRole)
        return postForm<CompliancePhoto>(
          `/compliance/shoots/${encodeURIComponent(shootId)}/photos-v2`,
          fd,
          signal,
        )
      },

      deletePhotoV2: (shootId: string, slotId: string) =>
        del<{ ok: boolean }>(
          `/compliance/shoots/${encodeURIComponent(shootId)}/photos-v2/${encodeURIComponent(slotId)}`,
        ),
    },
  }
}
