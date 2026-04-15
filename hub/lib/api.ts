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

// ─── Low-level fetch ────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  idToken: string | undefined,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}/api${path}`
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  }
  if (idToken) {
    headers["Authorization"] = `Bearer ${idToken}`
  }

  const res = await fetch(url, { ...options, headers })

  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new ApiError(res.status, body)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T

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
  site_code: string
  title: string
  performers: string
  categories: string
  tags: string
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

// ─── API client factory ──────────────────────────────────────────────────────

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
      }) => {
        const params = new URLSearchParams()
        if (filters?.status)   params.set("status",   filters.status)
        if (filters?.project)  params.set("project",  filters.project)
        if (filters?.priority) params.set("priority", filters.priority)
        if (filters?.assignee) params.set("assignee", filters.assignee)
        const qs = params.toString()
        return get<Ticket[]>(`/tickets/${qs ? `?${qs}` : ""}`)
      },
      stats: () => get<TicketStats>("/tickets/stats"),
      get: (id: string) => get<Ticket>(`/tickets/${id}`),
      create: (body: TicketCreate) => post<Ticket>("/tickets/", body),
      update: (id: string, body: TicketUpdate) => patch<Ticket>(`/tickets/${id}`, body),
    },

    scenes: {
      list: (filters?: { studio?: string; missing_only?: boolean; search?: string; page?: number; limit?: number }) => {
        const params = new URLSearchParams()
        if (filters?.studio) params.set("studio", filters.studio)
        if (filters?.missing_only) params.set("missing_only", "true")
        if (filters?.search) params.set("search", filters.search)
        if (filters?.page) params.set("page", String(filters.page))
        if (filters?.limit) params.set("limit", String(filters.limit))
        const qs = params.toString()
        return get<Scene[]>(`/scenes/${qs ? `?${qs}` : ""}`)
      },
      stats: () => get<SceneStats>("/scenes/stats"),
      get: (id: string) => get<Scene>(`/scenes/${id}`),
    },

    scripts: {
      list: (filters?: { studio?: string; tab_name?: string; needs_script?: boolean; search?: string }) => {
        const params = new URLSearchParams()
        if (filters?.studio) params.set("studio", filters.studio)
        if (filters?.tab_name) params.set("tab_name", filters.tab_name)
        if (filters?.needs_script) params.set("needs_script", "true")
        if (filters?.search) params.set("search", filters.search)
        const qs = params.toString()
        return get<Script[]>(`/scripts/${qs ? `?${qs}` : ""}`)
      },
      tabs: () => get<string[]>("/scripts/tabs"),
      save: (body: { tab_name: string; sheet_row: number; theme: string; plot: string; wardrobe_f?: string; wardrobe_m?: string }) =>
        post<{ ok: boolean }>("/scripts/save", body),
    },

    descriptions: {
      save: (body: { scene_id: string; description: string; meta_title?: string; meta_description?: string }) =>
        post<{ ok: boolean }>("/descriptions/save", body),
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
      save: (body: { studio: string; title: string; scene_ids: string[]; description?: string; notes?: string; target_sheet?: string; target_range?: string }) =>
        post<{ task_id: string; status: string }>("/compilations/save", body),
    },
  }
}
