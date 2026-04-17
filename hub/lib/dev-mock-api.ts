/**
 * Dev-only routing for API requests. Only imported when NODE_ENV !== production
 * AND DEV_AUTH_MOCK/NEXT_PUBLIC_DEV_AUTH_MOCK === "1".
 *
 * Maps request paths to fixtures in dev-fixtures.ts. Does just enough routing
 * to walk the UI — not a full API parity.
 */

import {
  MOCK_USER,
  MOCK_ALL_USERS,
  MOCK_SCENE_STATS,
  MOCK_APPROVALS,
  MOCK_SCRIPTS,
  MOCK_NOTIFICATIONS,
  MOCK_HEALTH,
  MOCK_TICKETS,
  MOCK_TICKET_STATS,
  MOCK_MODELS,
  MOCK_CALLSHEET_TABS,
  MOCK_SHOOT_DATES,
  MOCK_SCRIPT_TABS,
  MOCK_SCENES,
  filterScenes,
} from "./dev-fixtures"

// Simulated network latency so loading states aren't instant
const MOCK_DELAY = 120

function wait<T>(value: T, ms = MOCK_DELAY): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(value), ms))
}

function parseQuery(path: string): { base: string; params: URLSearchParams } {
  const qIdx = path.indexOf("?")
  if (qIdx === -1) return { base: path, params: new URLSearchParams() }
  return {
    base: path.slice(0, qIdx),
    params: new URLSearchParams(path.slice(qIdx + 1)),
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function mockApi<T>(path: string, _options: RequestInit): Promise<T> {
  const { base, params } = parseQuery(path)

  // ── Health ─────────────────────────────────────────────────────────────
  if (base === "/health") return wait(MOCK_HEALTH as unknown as T)

  // ── Users ─────────────────────────────────────────────────────────────
  if (base === "/users/me") return wait(MOCK_USER as unknown as T)
  if (base === "/users/")   return wait(MOCK_ALL_USERS as unknown as T)

  // ── Scenes ────────────────────────────────────────────────────────────
  if (base === "/scenes/stats") return wait(MOCK_SCENE_STATS as unknown as T)
  if (base === "/scenes/") {
    const filters = {
      studio: params.get("studio") ?? undefined,
      missing_only: params.get("missing_only") === "true",
      search: params.get("search") ?? undefined,
      limit: params.get("limit") ? parseInt(params.get("limit")!) : undefined,
    }
    return wait(filterScenes(filters) as unknown as T)
  }
  const namingMatch = base.match(/^\/scenes\/([^/]+)\/naming-issues$/)
  if (namingMatch) {
    return wait({ scene_id: namingMatch[1], issues: [], ok: true } as unknown as T)
  }

  // ── Approvals ─────────────────────────────────────────────────────────
  if (base === "/approvals/") {
    const status = params.get("status")
    const list = status ? MOCK_APPROVALS.filter(a => a.status === status) : MOCK_APPROVALS
    return wait(list as unknown as T)
  }
  const decideMatch = base.match(/^\/approvals\/([^/]+)$/)
  if (decideMatch) {
    // Treat PATCH as decide; GET as fetch one
    const appr = MOCK_APPROVALS.find(a => a.approval_id === decideMatch[1])
    return wait((appr ?? MOCK_APPROVALS[0]) as unknown as T)
  }

  // ── Scripts ───────────────────────────────────────────────────────────
  if (base === "/scripts/tabs") return wait(MOCK_SCRIPT_TABS as unknown as T)
  if (base === "/scripts/") {
    const needs = params.get("needs_script") === "true"
    return wait((needs ? MOCK_SCRIPTS : MOCK_SCRIPTS) as unknown as T)
  }

  // ── Tickets ───────────────────────────────────────────────────────────
  if (base === "/tickets/") return wait(MOCK_TICKETS as unknown as T)
  if (base === "/tickets/stats") return wait(MOCK_TICKET_STATS as unknown as T)

  // ── Notifications ─────────────────────────────────────────────────────
  if (base === "/notifications/") return wait(MOCK_NOTIFICATIONS as unknown as T)
  if (base === "/notifications/unread-count") {
    return wait({ count: MOCK_NOTIFICATIONS.filter(n => n.read === 0).length } as unknown as T)
  }
  if (base === "/notifications/mark-read") return wait({ updated: 3 } as unknown as T)

  // ── Models ────────────────────────────────────────────────────────────
  if (base === "/models/") return wait(MOCK_MODELS as unknown as T)

  // ── Call sheets ───────────────────────────────────────────────────────
  if (base === "/call-sheets/tabs")   return wait(MOCK_CALLSHEET_TABS as unknown as T)
  if (base === "/call-sheets/dates")  return wait(MOCK_SHOOT_DATES as unknown as T)

  // ── Compilations ──────────────────────────────────────────────────────
  if (base === "/compilations/scenes") return wait(MOCK_SCENES as unknown as T)
  if (base === "/compilations/existing") return wait([] as unknown as T)

  // ── Sync ──────────────────────────────────────────────────────────────
  if (base === "/sync/status") return wait([] as unknown as T)

  // eslint-disable-next-line no-console
  console.warn(`[dev-mock-api] Unmapped path: ${path}`)
  return wait(null as unknown as T, 60)
}
