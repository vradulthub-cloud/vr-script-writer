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
  MOCK_SHOOTS,
  filterScenes,
} from "./dev-fixtures"

// Simulated network latency so loading states aren't instant
const MOCK_DELAY = 120

function wait<T>(value: T, ms = MOCK_DELAY): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(value), ms))
}

// In-memory calendar events for dev-mock. Keeps create/delete flows working
// without a backend, and resets on hard reload (unlike localStorage — which
// is exactly what we're migrating AWAY from).
type MockCalEvent = {
  event_id: string
  date: string
  title: string
  kind: string
  color: string
  notes: string
  created_by: string
  created_at: string
}
const MOCK_CAL_EVENTS: MockCalEvent[] = []

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
  if (base === "/users/") {
    const method = (_options.method || "GET").toUpperCase()
    if (method === "GET") return wait(MOCK_ALL_USERS as unknown as T)
    if (method === "POST") {
      const body = _options.body ? JSON.parse(_options.body as string) : {}
      const u = {
        email: (body.email ?? "").toLowerCase(),
        name: body.name ?? "",
        role: body.role ?? "editor",
        allowed_tabs: body.allowed_tabs ?? "ALL",
      }
      ;(MOCK_ALL_USERS as Array<typeof u>).push(u)
      return wait(u as unknown as T)
    }
  }
  // /users/{email} — DELETE removes from the mock array
  if (base.startsWith("/users/") && (_options.method || "").toUpperCase() === "DELETE") {
    const email = decodeURIComponent(base.slice("/users/".length)).toLowerCase()
    const arr = MOCK_ALL_USERS as Array<{ email: string }>
    const idx = arr.findIndex(u => u.email.toLowerCase() === email)
    if (idx >= 0) arr.splice(idx, 1)
    return wait(undefined as unknown as T)
  }
  // ── Per-source sync (admin) ───────────────────────────────────────────
  if (base.startsWith("/sync/trigger/")) {
    const source = decodeURIComponent(base.slice("/sync/trigger/".length))
    return wait({ source, row_count: 42, status: "ok" } as unknown as T)
  }

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
  const generateTitleMatch = base.match(/^\/scenes\/([^/]+)\/generate-title$/)
  if (generateTitleMatch) {
    // Deterministic-feeling mock — the point is to exercise the UI flow, not
    // actually be creative. Hash the scene id into one of a dozen canned titles.
    const sid = generateTitleMatch[1]
    const pool = [
      "Under Her Spell", "Stay After Class", "The Long Game", "Behind Closed Doors",
      "Private Practice", "Perfectly Still", "Heat By Design", "Earning It",
      "Deep Focus", "The Right Fit", "All In", "Nailing the Interview",
    ]
    let h = 0
    for (const ch of sid) h = (h * 31 + ch.charCodeAt(0)) >>> 0
    return wait({ title: pool[h % pool.length] } as unknown as T)
  }
  const updateTitleMatch = base.match(/^\/scenes\/([^/]+)\/title$/)
  if (updateTitleMatch) {
    return wait({ ok: true } as unknown as T)
  }
  if (base === "/scripts/title-generate") {
    return wait({ title: "Checked In" } as unknown as T)
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
  if (base === "/scripts/validate") {
    // Parity mock: flag the same classic "slop" phrases the real validator
    // catches so the UI rule-panel has something to render.
    const input = (_options?.body ?? "") as string
    const text = typeof input === "string" ? input : ""
    const violations: string[] = []
    if (/\bimpossibly\b/i.test(text)) violations.push("Drop vague intensifier: 'impossibly'")
    if (/\belectric\s+charge\b/i.test(text)) violations.push("Cliché metaphor: 'electric charge'")
    if (/\btension\s+in\s+the\s+air\b/i.test(text)) violations.push("Cliché: 'tension in the air'")
    return wait({ violations, passed: violations.length === 0 } as unknown as T)
  }
  if (base === "/scripts/save") return wait({ id: 1, status: "saved" } as unknown as T)
  if (base === "/scripts/") {
    const needs = params.get("needs_script") === "true"
    return wait((needs ? MOCK_SCRIPTS : MOCK_SCRIPTS) as unknown as T)
  }

  // ── Tickets ───────────────────────────────────────────────────────────
  if (base === "/tickets/") return wait(MOCK_TICKETS as unknown as T)
  if (base === "/tickets/stats") return wait(MOCK_TICKET_STATS as unknown as T)

  // ── Calendar events ───────────────────────────────────────────────────
  if (base === "/calendar-events/") {
    const method = (_options.method || "GET").toUpperCase()
    if (method === "GET") {
      const from = params.get("from")
      const to = params.get("to")
      const filtered = MOCK_CAL_EVENTS.filter(e =>
        (!from || e.date >= from) && (!to || e.date <= to),
      )
      return wait(filtered as unknown as T)
    }
    if (method === "POST") {
      const body = _options.body ? JSON.parse(_options.body as string) : {}
      const ev: MockCalEvent = {
        event_id: `evt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        date: body.date ?? "",
        title: (body.title ?? "").trim(),
        kind: (body.kind ?? "").trim(),
        color: (body.color ?? "").trim(),
        notes: (body.notes ?? "").trim(),
        created_by: "Dev Admin",
        created_at: new Date().toISOString(),
      }
      MOCK_CAL_EVENTS.push(ev)
      return wait(ev as unknown as T)
    }
  }
  if (base.startsWith("/calendar-events/") && (_options.method || "").toUpperCase() === "DELETE") {
    const id = decodeURIComponent(base.slice("/calendar-events/".length))
    const idx = MOCK_CAL_EVENTS.findIndex(e => e.event_id === id)
    if (idx >= 0) MOCK_CAL_EVENTS.splice(idx, 1)
    return wait(undefined as unknown as T)
  }

  // ── Notifications ─────────────────────────────────────────────────────
  if (base === "/notifications/") return wait(MOCK_NOTIFICATIONS as unknown as T)
  if (base === "/notifications/unread-count") {
    return wait({ count: MOCK_NOTIFICATIONS.filter(n => n.read === 0).length } as unknown as T)
  }
  if (base === "/notifications/mark-read") return wait({ updated: 3 } as unknown as T)

  // ── Models ────────────────────────────────────────────────────────────
  if (base === "/models/") return wait(MOCK_MODELS as unknown as T)
  if (base === "/models/trending") {
    // Small fixture so /research doesn't show the "could not load" banner
    // in mock mode. Real backend serves SLR/VRP scrape results.
    return wait([
      { name: "Liv Wilder",   platform: "SLR", scenes: "48", followers: "12.4k", views: "3.2M",  photo_url: "https://picsum.photos/seed/liv/160/200",   profile_url: "#" },
      { name: "Nova Reign",   platform: "VRP", scenes: "31", followers: "8.7k",  views: "1.1M",  photo_url: "https://picsum.photos/seed/nova/160/200",  profile_url: "#" },
      { name: "Cass Monroe",  platform: "SLR", scenes: "22", followers: "6.2k",  views: "740k",  photo_url: "https://picsum.photos/seed/cass/160/200",  profile_url: "#" },
      { name: "River Black",  platform: "VRP", scenes: "17", followers: "4.1k",  views: "520k",  photo_url: "https://picsum.photos/seed/river/160/200", profile_url: "#" },
      { name: "Sable Storm",  platform: "SLR", scenes: "12", followers: "3.6k",  views: "390k",  photo_url: "https://picsum.photos/seed/sable/160/200", profile_url: "#" },
    ] as unknown as T)
  }

  // ── Call sheets ───────────────────────────────────────────────────────
  // ── Titles — Model Name PNG ───────────────────────────────────────
  if (base === "/titles/model-name") {
    // 1x1 transparent PNG — enough for the UI to render without the
    // real PIL renderer, which needs local fonts.
    const pixel =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    return wait({ data_url: `data:image/png;base64,${pixel}` } as unknown as T)
  }

  // ── Descriptions regen ────────────────────────────────────────────
  if (base === "/descriptions/regenerate-paragraph") {
    return wait({
      paragraph:
        "Her gaze finds yours through the dim light — deliberate, unhurried — and every thought you arrived with evaporates the moment she steps closer.",
    } as unknown as T)
  }

  if (base === "/call-sheets/tabs")   return wait(MOCK_CALLSHEET_TABS as unknown as T)
  if (base === "/call-sheets/dates")  return wait(MOCK_SHOOT_DATES as unknown as T)
  if (base === "/call-sheets/generate") {
    return wait({
      doc_url: "https://docs.google.com/document/d/mock-call-sheet",
      title: "Mock Call Sheet",
    } as unknown as T)
  }

  // ── Compilations ──────────────────────────────────────────────────────
  if (base === "/compilations/scenes") return wait(MOCK_SCENES as unknown as T)
  if (base === "/compilations/existing") {
    const studio = params.get("studio") ?? "FuckPassVR"
    const studioKey: Record<string, string> = {
      FuckPassVR: "FPVR", VRHush: "VRH", VRAllure: "VRA", NaughtyJOI: "NJOI",
    }
    const key = studioKey[studio] ?? "FPVR"
    return wait([
      {
        comp_id: `${key}-C0002`,
        title: "Best of Blondes Vol. 3",
        volume: "Vol. 3",
        status: "Draft",
        studio_key: key,
        created: "2026-04-18 14:22",
        created_by: "Drew",
        updated: "2026-04-18 14:22",
        description: "A curated set of our most-requested blonde performers.",
        notes: "",
        scene_count: 3,
        scenes: [
          { scene_id: `${key}0369`, scene_num: 1, title: "Sample Scene 1", performers: "Ava Addams", slr_link: "", mega_link: "https://mega.nz/folder/AAAA#demo1" },
          { scene_id: `${key}0412`, scene_num: 2, title: "Sample Scene 2", performers: "Mia Khalifa", slr_link: "", mega_link: "https://mega.nz/folder/BBBB#demo2" },
          { scene_id: `${key}0455`, scene_num: 3, title: "Sample Scene 3", performers: "Riley Reid", slr_link: "", mega_link: "" },
        ],
      },
      {
        comp_id: `${key}-C0001`,
        title: "Rainy Night In",
        volume: "New",
        status: "Published",
        studio_key: key,
        created: "2026-03-02 09:11",
        created_by: "Drew",
        updated: "2026-03-05 10:04",
        description: "",
        notes: "",
        scene_count: 2,
        scenes: [
          { scene_id: `${key}0291`, scene_num: 1, title: "Rain Scene A", performers: "Katie Kush", slr_link: "", mega_link: "https://mega.nz/folder/CCCC#demo3" },
          { scene_id: `${key}0305`, scene_num: 2, title: "Rain Scene B", performers: "Lulu Chu", slr_link: "", mega_link: "https://mega.nz/folder/DDDD#demo4" },
        ],
      },
    ] as unknown as T)
  }

  // ── Shoots ────────────────────────────────────────────────────────────
  if (base === "/shoots/") {
    const studio = params.get("studio")
    const includeCancelled = params.get("include_cancelled") === "true"
    let list = MOCK_SHOOTS
    if (!includeCancelled) list = list.filter(s => s.status !== "cancelled")
    if (studio) list = list.filter(s => s.scenes.some(sc => sc.studio === studio))
    return wait(list as unknown as T)
  }
  const shootGet = base.match(/^\/shoots\/([^/]+)$/)
  if (shootGet) {
    const s = MOCK_SHOOTS.find(x => x.shoot_id === shootGet[1]) ?? MOCK_SHOOTS[0]
    return wait(s as unknown as T)
  }
  const revalidateMatch = base.match(/^\/shoots\/([^/]+)\/scenes\/(\d+)\/assets\/([^/]+)\/revalidate$/)
  if (revalidateMatch) {
    const [, shootId, posStr, assetType] = revalidateMatch
    const pos = parseInt(posStr)
    const shoot = MOCK_SHOOTS.find(s => s.shoot_id === shootId)
    const scene = shoot?.scenes.find(sc => sc.position === pos)
    const asset = scene?.assets.find(a => a.asset_type === assetType)
    if (asset) {
      const refreshed = {
        ...asset,
        last_checked_at: new Date().toISOString(),
        validity: asset.validity.filter(v => v.status !== "fail"),
      }
      return wait(refreshed as unknown as T)
    }
    return wait(null as unknown as T)
  }

  // ── Sync ──────────────────────────────────────────────────────────────
  if (base === "/sync/status") return wait([] as unknown as T)
  if (base === "/sync/trigger") {
    return wait({
      status: "completed",
      results: { scenes: 1274, scripts: 482, models: 1830, shoots: 12 },
    } as unknown as T)
  }

  // eslint-disable-next-line no-console
  console.warn(`[dev-mock-api] Unmapped path: ${path}`)
  return wait(null as unknown as T, 60)
}
