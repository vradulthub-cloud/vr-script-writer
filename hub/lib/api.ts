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
  }
}
