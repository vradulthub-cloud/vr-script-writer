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
  MOCK_NOTIFICATION_PREFS,
  MOCK_HEALTH,
  MOCK_TICKETS,
  MOCK_TICKET_STATS,
  MOCK_MODELS,
  MOCK_CALLSHEET_TABS,
  MOCK_SHOOT_DATES,
  MOCK_SCRIPT_TABS,
  MOCK_SCENES,
  MOCK_SHOOTS,
  MOCK_COMPLIANCE_SHOOTS,
  MOCK_SIGNATURE_HITS,
  MOCK_MEGA_LEGAL_FILES,
  filterScenes,
} from "./dev-fixtures"

// Simulated network latency so loading states aren't instant
const MOCK_DELAY = 120

// In-memory store: which talents have signed which shoot in this dev session.
// Survives navigation but resets on page reload. Just enough to demo the
// per-talent flow without spinning up a real backend.
type MockSigned = {
  talent_role: string
  talent_slug: string
  talent_display: string
  legal_name: string
  signed_at: string
  pdf_mega_path: string
}
const mockSignedByShoot = new Map<string, MockSigned[]>()

// In-memory store for server-persisted compliance photos (TKT-0151).
// Each entry mirrors a CompliancePhoto from the API. We keep the bytes as a
// blob URL so the iPad UI can re-render thumbnails on reload — the URL field
// the API would normally hold is replaced by the local blob URL in dev.
type MockPhoto = {
  slot_id: string
  talent_role: string
  label: string
  mime_type: string
  file_size: number
  uploaded_at: string
  mega_path: string
  url: string
}
const mockPhotosByShoot = new Map<string, MockPhoto[]>()

// In-memory mock state for the integrations admin panel — lets the Save
// button give visible feedback in dev without a real backend. Resets on
// hard reload.
let mockTeamsWebhook = ""
let mockHubBaseUrl = "http://localhost:3001"

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

// Stateful prompt overrides for dev-mock. Each entry mirrors the backend
// PromptEntry shape so the editor exercises the full save/revert flow.
type MockPrompt = {
  key: string
  label: string
  group: string
  content: string
  default: string
  is_overridden: boolean
  updated_by: string
  updated_at: string
}
const T_VRH = "You are a creative title writer for VRHush, a premium VR adult content studio. Generate exactly ONE scene title that reflects the actual plot/theme you're given. The title MUST hook into a concrete hook from the script — the setup, the setting, a prop, the wardrobe, the role, or a beat of the action. Form: 2-4 words, title case, clever wordplay/double-entendre preferred over literal description, no performer names, no all-caps. Respond with ONLY the title — no explanation, no quotes."
const T_FPVR = "You are a creative title writer for FuckPassVR, a premium VR travel-and-intimacy studio. If the script names a destination or city, lean into it. Form: 2-5 words, title case, clever wordplay preferred. Respond with ONLY the title."
const T_VRA = "You are a creative title writer for VRAllure. Sensual, intimate, soft tone. Each title MUST reference something concrete from the script — wardrobe, prop, gesture, or mood. Form: 2-4 words, title case."
const T_NJOI = "You are a creative title writer for NaughtyJOI. Generate a PAIRED title using the performer's first name. Two lines: line 1 soft/intimate, line 2 more commanding."
const D_FPVR = "# PERSONALITY:\nYou are an expert adult copywriter for FuckPassVR. Write sexual, filthy, deeply arousing scene descriptions optimized for SEO and VR immersion.\n\n# WRITING STANDARDS:\n1. Active voice, visceral verbs.\n2. 2-paragraph format with bold subheadings.\n3. Reference 8K VR naturally."
const D_VRH = "# PERSONALITY:\nYou are a copywriter for VRHush — raw, kinetic, no wasted words. Single-paragraph 100-140 words. 2nd-person POV throughout. Close with 'Taste her on VRHush now.'"
const D_VRA = "# PERSONALITY:\nYou are a sensual copywriter for VRAllure. Intimate, whisper-close. 60-90 words. Focus on breath, warmth, fingertips."
const D_NJOI = "# PERSONALITY:\nYou are a teasing copywriter for NaughtyJOI. Must include at least one short performer quote. Tease-build-countdown-release rhythm."
const SCRIPT_SYS = "You are a professional VR adult film script writer for VRHush and FuckPassVR. Cinematic, intimate, director-ready. Use exactly these section headers: THEME, PLOT, SHOOT LOCATION, SET DESIGN, PROPS, WARDROBE - FEMALE, WARDROBE - MALE."
const MOCK_PROMPTS: MockPrompt[] = [
  { key: "title.VRHush",     label: "Title — VRHush",     group: "Titles",       content: T_VRH,  default: T_VRH,  is_overridden: false, updated_by: "", updated_at: "" },
  { key: "title.FuckPassVR", label: "Title — FuckPassVR", group: "Titles",       content: T_FPVR, default: T_FPVR, is_overridden: false, updated_by: "", updated_at: "" },
  { key: "title.VRAllure",   label: "Title — VRAllure",   group: "Titles",       content: T_VRA,  default: T_VRA,  is_overridden: false, updated_by: "", updated_at: "" },
  { key: "title.NaughtyJOI", label: "Title — NaughtyJOI", group: "Titles",       content: T_NJOI, default: T_NJOI, is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc.FPVR",        label: "Description — FuckPassVR", group: "Descriptions", content: D_FPVR, default: D_FPVR, is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc.VRH",         label: "Description — VRHush",     group: "Descriptions", content: D_VRH,  default: D_VRH,  is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc.VRA",         label: "Description — VRAllure",   group: "Descriptions", content: D_VRA,  default: D_VRA,  is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc.NJOI",        label: "Description — NaughtyJOI", group: "Descriptions", content: D_NJOI, default: D_NJOI, is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc_comp.FPVR",   label: "Compilation Desc — FuckPassVR", group: "Compilations", content: D_FPVR, default: D_FPVR, is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc_comp.VRH",    label: "Compilation Desc — VRHush",     group: "Compilations", content: D_VRH,  default: D_VRH,  is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc_comp.VRA",    label: "Compilation Desc — VRAllure",   group: "Compilations", content: D_VRA,  default: D_VRA,  is_overridden: false, updated_by: "", updated_at: "" },
  { key: "desc_comp.NJOI",   label: "Compilation Desc — NaughtyJOI", group: "Compilations", content: D_NJOI, default: D_NJOI, is_overridden: false, updated_by: "", updated_at: "" },
  { key: "script.system",    label: "Script Generation — System Prompt", group: "Scripts", content: SCRIPT_SYS, default: SCRIPT_SYS, is_overridden: false, updated_by: "", updated_at: "" },
]

function parseQuery(path: string): { base: string; params: URLSearchParams } {
  const qIdx = path.indexOf("?")
  if (qIdx === -1) return { base: path, params: new URLSearchParams() }
  return {
    base: path.slice(0, qIdx),
    params: new URLSearchParams(path.slice(qIdx + 1)),
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function mockApi<T>(path: string, init: RequestInit): Promise<T> {
  const { base, params } = parseQuery(path)

  // ── Health ─────────────────────────────────────────────────────────────
  if (base === "/health") return wait(MOCK_HEALTH as unknown as T)

  // ── Users ─────────────────────────────────────────────────────────────
  if (base === "/users/me") return wait(MOCK_USER as unknown as T)
  if (base === "/users/teammates") {
    const all = MOCK_ALL_USERS as Array<{ email: string; name: string }>
    return wait(all.map(u => ({ email: u.email, name: u.name })) as unknown as T)
  }
  if (base === "/users/") {
    const method = (init.method || "GET").toUpperCase()
    if (method === "GET") return wait(MOCK_ALL_USERS as unknown as T)
    if (method === "POST") {
      const body = init.body ? JSON.parse(init.body as string) : {}
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
  if (base.startsWith("/users/") && (init.method || "").toUpperCase() === "DELETE") {
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
  if (base === "/scenes/mega-refresh" && (init.method || "").toUpperCase() === "POST") {
    // Real backend kicks off a ~50–60s scan. Mock returns instantly so the
    // dashboard's Refresh button can be exercised without a real backend.
    return wait({ status: "triggered", message: "Mock MEGA scan started" } as unknown as T)
  }
  if (base === "/scenes/stats") return wait(MOCK_SCENE_STATS as unknown as T)
  if (base === "/scenes/recent") {
    const studios = (params.get("studios") ?? "").split(",").map(s => s.trim()).filter(Boolean)
    const perStudio = params.get("per_studio") ? parseInt(params.get("per_studio")!) : 5
    const missingOnly = params.get("missing_only") !== "false"
    const flat = studios.flatMap(studio =>
      filterScenes({ studio, missing_only: missingOnly, limit: perStudio }),
    )
    return wait(flat as unknown as T)
  }
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
  const storyboardMatch = base.match(/^\/scenes\/([^/]+)\/storyboard$/)
  if (storyboardMatch) {
    // Realistic mock: deterministic count keyed off the scene id so the
    // strip shows a consistent number of frames across reloads.
    const sid = storyboardMatch[1]
    let h = 0
    for (const ch of sid) h = (h * 31 + ch.charCodeAt(0)) >>> 0
    const count = (h % 12) + 4 // 4..15 frames
    const files = Array.from({ length: count }, (_, i) => ({
      filename: `${sid}-Photos_${String(i + 1).padStart(3, "0")}.jpg`,
      size: 1_000_000 + (h % 500_000),
    }))
    return wait({ scene_id: sid, files } as unknown as T)
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
    const input = (init?.body ?? "") as string
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
  if (base === "/tickets/") {
    const typeFilter = params.get("type")
    const statusFilter = params.get("status")
    const limit = params.get("limit") ? parseInt(params.get("limit")!) : undefined
    let list = MOCK_TICKETS as typeof MOCK_TICKETS
    if (typeFilter) list = list.filter(t => t.type === typeFilter)
    if (statusFilter) list = list.filter(t => t.status === statusFilter)
    if (limit) list = list.slice(0, limit)
    return wait(list as unknown as T)
  }
  if (base === "/tickets/stats") return wait(MOCK_TICKET_STATS as unknown as T)

  // ── AI Prompts ────────────────────────────────────────────────────────
  if (base === "/prompts/") {
    return wait(MOCK_PROMPTS as unknown as T)
  }
  if (base.startsWith("/prompts/")) {
    const method = (init.method || "GET").toUpperCase()
    const key = decodeURIComponent(base.slice("/prompts/".length))
    if (method === "GET") {
      const p = MOCK_PROMPTS.find(x => x.key === key)
      if (!p) return wait(null as unknown as T)
      return wait(p as unknown as T)
    }
    if (method === "PUT") {
      const body = init.body ? JSON.parse(init.body as string) : {}
      const idx = MOCK_PROMPTS.findIndex(x => x.key === key)
      if (idx >= 0) {
        MOCK_PROMPTS[idx] = {
          ...MOCK_PROMPTS[idx],
          content: body.content ?? "",
          is_overridden: true,
          updated_by: "Dev Admin",
          updated_at: new Date().toISOString(),
        }
        return wait(MOCK_PROMPTS[idx] as unknown as T)
      }
      return wait(null as unknown as T)
    }
    if (method === "DELETE") {
      const idx = MOCK_PROMPTS.findIndex(x => x.key === key)
      if (idx >= 0) {
        MOCK_PROMPTS[idx] = {
          ...MOCK_PROMPTS[idx],
          content: MOCK_PROMPTS[idx].default,
          is_overridden: false,
          updated_by: "",
          updated_at: "",
        }
      }
      return wait(undefined as unknown as T)
    }
  }

  // ── Background tasks ──────────────────────────────────────────────────
  if (base === "/tasks/") {
    const statusFilter = params.get("status")
    const limit = params.get("limit") ? parseInt(params.get("limit")!) : 50
    const all = [
      { task_id: "task-aa11bb22cc33", task_type: "script_gen",  status: "running",   progress: 0.62, created_at: "2026-04-21T16:42:00Z", started_at: "2026-04-21T16:42:01Z", completed_at: "", created_by: "Drew",   error: "" },
      { task_id: "task-44dd55ee66ff", task_type: "desc_gen",    status: "running",   progress: 0.18, created_at: "2026-04-21T16:41:30Z", started_at: "2026-04-21T16:41:31Z", completed_at: "", created_by: "Editor", error: "" },
      { task_id: "task-7788aabbccdd", task_type: "mega_scan",   status: "completed", progress: 1.0,  created_at: "2026-04-21T16:30:00Z", started_at: "2026-04-21T16:30:01Z", completed_at: "2026-04-21T16:38:12Z", created_by: "system", error: "" },
      { task_id: "task-eeff00112233", task_type: "title_gen",   status: "completed", progress: 1.0,  created_at: "2026-04-21T16:18:00Z", started_at: "2026-04-21T16:18:00Z", completed_at: "2026-04-21T16:19:05Z", created_by: "Drew",   error: "" },
      { task_id: "task-44556677ee99", task_type: "comp_export", status: "failed",    progress: 0.45, created_at: "2026-04-21T15:55:00Z", started_at: "2026-04-21T15:55:01Z", completed_at: "2026-04-21T15:56:30Z", created_by: "Editor", error: "MEGA timeout after 60s" },
      { task_id: "task-998877665544", task_type: "script_gen",  status: "completed", progress: 1.0,  created_at: "2026-04-21T15:42:00Z", started_at: "2026-04-21T15:42:01Z", completed_at: "2026-04-21T15:43:50Z", created_by: "Drew",   error: "" },
      { task_id: "task-aabbccdd1122", task_type: "desc_gen",    status: "pending",   progress: 0,    created_at: "2026-04-21T16:43:10Z", started_at: "", completed_at: "", created_by: "Drew", error: "" },
    ]
    let list = all
    if (statusFilter) list = list.filter(t => t.status === statusFilter)
    return wait(list.slice(0, limit) as unknown as T)
  }
  if (base === "/tasks/stats") {
    return wait({ pending: 1, running: 2, completed: 3, failed: 1, total: 7 } as unknown as T)
  }

  // ── Calendar events ───────────────────────────────────────────────────
  if (base === "/calendar-events/") {
    const method = (init.method || "GET").toUpperCase()
    if (method === "GET") {
      const from = params.get("from")
      const to = params.get("to")
      const filtered = MOCK_CAL_EVENTS.filter(e =>
        (!from || e.date >= from) && (!to || e.date <= to),
      )
      return wait(filtered as unknown as T)
    }
    if (method === "POST") {
      const body = init.body ? JSON.parse(init.body as string) : {}
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
  if (base.startsWith("/calendar-events/") && (init.method || "").toUpperCase() === "DELETE") {
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
  if (base === "/notifications/prefs") {
    const method = (init.method || "GET").toUpperCase()
    if (method === "GET") return wait(MOCK_NOTIFICATION_PREFS as unknown as T)
    if (method === "PUT") {
      // Echo the change back into the in-memory mock so toggles "stick" for
      // the rest of the session. Best-effort — no parsing on bad bodies.
      try {
        const body = JSON.parse((init.body as string) ?? "{}") as { event_type?: string; channels?: string[]; enabled?: boolean }
        const idx = MOCK_NOTIFICATION_PREFS.findIndex(p => p.event_type === body.event_type)
        if (idx >= 0 && body.event_type) {
          MOCK_NOTIFICATION_PREFS[idx] = {
            ...MOCK_NOTIFICATION_PREFS[idx],
            channels: body.channels ?? MOCK_NOTIFICATION_PREFS[idx].channels,
            enabled: body.enabled ?? MOCK_NOTIFICATION_PREFS[idx].enabled,
          }
        }
      } catch { /* fall through and just return current state */ }
      return wait(MOCK_NOTIFICATION_PREFS as unknown as T)
    }
  }

  // ── Integrations (admin) ───────────────────────────────────────────────
  // In-memory mock state for integrations so the admin panel "Save" buttons
  // give visible feedback in dev. Resets on hard reload.
  if (base === "/integrations/teams") {
    const method = (init.method || "GET").toUpperCase()
    if (method === "GET") {
      return wait({
        configured: !!mockTeamsWebhook,
        url_preview: mockTeamsWebhook ? mockTeamsWebhook.slice(0, 24) + "…" : "",
        updated_by: mockTeamsWebhook ? "Dev Admin" : "",
        updated_at: mockTeamsWebhook ? new Date().toISOString() : "",
      } as unknown as T)
    }
    if (method === "PUT") {
      try {
        const body = JSON.parse((init.body as string) ?? "{}") as { url?: string }
        mockTeamsWebhook = (body.url ?? "").trim()
      } catch { /* ignore */ }
      return wait({
        configured: !!mockTeamsWebhook,
        url_preview: mockTeamsWebhook ? mockTeamsWebhook.slice(0, 24) + "…" : "",
      } as unknown as T)
    }
  }
  if (base === "/integrations/teams/test") {
    return wait({ ok: !!mockTeamsWebhook } as unknown as T)
  }
  if (base === "/integrations/hub-base-url") {
    const method = (init.method || "GET").toUpperCase()
    if (method === "GET") {
      return wait({ url: mockHubBaseUrl, updated_by: "Dev Admin", updated_at: "2026-05-03T00:00:00Z" } as unknown as T)
    }
    if (method === "PUT") {
      try {
        const body = JSON.parse((init.body as string) ?? "{}") as { url?: string }
        mockHubBaseUrl = (body.url ?? "").trim()
      } catch { /* ignore */ }
      return wait({ url: mockHubBaseUrl } as unknown as T)
    }
  }

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
  // ── Titles — Local AI (FLUX + RMBG via Windows ComfyUI) ───────────
  if (base === "/titles/flux-local") {
    const body = init.body ? JSON.parse(init.body as string) : {}
    const seed = body.seed && body.seed > 0 ? body.seed : 424242
    // 1x1 transparent PNG — real generation needs ComfyUI online.
    const pixel =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    return wait({
      data_url: `data:image/png;base64,${pixel}`,
      seed,
      error: null,
    } as unknown as T)
  }
  if (base === "/titles/flux-styles") {
    // Mirror the backend gate: trained-style only appears when the env var
    // is set, matching FLUX_TRAINED_STYLE_ENABLED on the FastAPI side.
    const trainedEnabled =
      typeof process !== "undefined" &&
      process.env.NEXT_PUBLIC_FLUX_TRAINED_STYLE_ENABLED === "1"
    const styles = [
      { key: "gold-leaf",     label: "Gold leaf" },
      { key: "chrome",        label: "Chrome" },
      { key: "marble",        label: "Marble" },
      { key: "vintage-film",  label: "Vintage film" },
      { key: "holographic",   label: "Holographic" },
      { key: "brushed-steel", label: "Brushed steel" },
      ...(trainedEnabled ? [{ key: "trained-style", label: "Trained style" }] : []),
    ]
    return wait(styles as unknown as T)
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
          { scene_id: `${key}0369`, scene_num: 1, title: "Sample Scene 1", performers: "Ava Addams", slr_link: "", mega_link: `https://${key.toLowerCase()}.s3.g.s4.mega.io/${key}0369/Videos/sample-1.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=604800&X-Amz-Signature=demo1` },
          { scene_id: `${key}0412`, scene_num: 2, title: "Sample Scene 2", performers: "Mia Khalifa", slr_link: "", mega_link: `https://${key.toLowerCase()}.s3.g.s4.mega.io/${key}0412/Videos/sample-2.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=604800&X-Amz-Signature=demo2` },
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
  // PATCH /compilations/{comp_id} — echo back the patched fields so the modal
  // can confirm a successful save in dev-mock without a real backend. If the
  // request includes an `if_match` whose title is the magic string
  // "__force_conflict__", simulate a 409 so the conflict UI is testable.
  const compPatch = base.match(/^\/compilations\/([A-Z]+-C\d{4})$/)
  if (compPatch && (init.method || "").toUpperCase() === "PATCH") {
    const comp_id = compPatch[1]
    const body = init.body ? JSON.parse(init.body as string) : {}
    if (body.if_match?.title === "__force_conflict__") {
      const { ApiError } = await import("./api")
      throw new ApiError(409, JSON.stringify({
        detail: {
          message: "Compilation was modified by someone else.",
          current: {
            title: "Best of Blondes Vol. 3 (their edit)",
            volume: "Vol. 3",
            status: "Published",
            description: "Updated by another editor while you were typing.",
          },
        },
      }))
    }
    return wait({
      status: "ok",
      comp_id,
      title: body.title ?? "",
      volume: body.volume ?? "",
      comp_status: body.status ?? "",
      description: body.description ?? "",
    } as unknown as T)
  }
  // PATCH /compilations/{comp_id}/scenes — echo back the new scene list so the
  // modal's optimistic mutation has something to confirm against (TKT-0147).
  const compScenesPatch = base.match(/^\/compilations\/([A-Z]+-C\d{4})\/scenes$/)
  if (compScenesPatch && (init.method || "").toUpperCase() === "PATCH") {
    const comp_id = compScenesPatch[1]
    const body = init.body ? JSON.parse(init.body as string) : {}
    const scene_ids = Array.isArray(body.scene_ids) ? body.scene_ids : []
    return wait({
      status: "ok",
      comp_id,
      scene_count: scene_ids.length,
      scene_ids,
    } as unknown as T)
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
  if (base === "/sync/status") {
    // Return rows so the SyncPanel doesn't blank itself in dev mode after
    // its mount-time refresh — initial data comes from /health.syncs.
    return wait([
      { source: "scenes",        last_synced_at: "2026-04-21T18:00:00Z", row_count: 1274, status: "ok",    error: "" },
      { source: "scripts",       last_synced_at: "2026-04-21T17:55:00Z", row_count: 186,  status: "ok",    error: "" },
      { source: "tickets",       last_synced_at: "2026-04-21T17:50:00Z", row_count: 47,   status: "ok",    error: "" },
      { source: "notifications", last_synced_at: "2026-04-21T17:48:00Z", row_count: 23,   status: "ok",    error: "" },
      { source: "approvals",     last_synced_at: "2026-04-21T17:42:00Z", row_count: 5,    status: "ok",    error: "" },
      { source: "users",         last_synced_at: "2026-04-21T17:30:00Z", row_count: 4,    status: "ok",    error: "" },
      { source: "bookings",      last_synced_at: "2026-04-21T17:00:00Z", row_count: 412,  status: "ok",    error: "" },
    ] as unknown as T)
  }
  if (base === "/sync/trigger") {
    return wait({
      status: "completed",
      results: { scenes: 1274, scripts: 482, models: 1830, shoots: 12 },
    } as unknown as T)
  }

  // ── Compliance: admin endpoints (TKT-0153) ────────────────────────────
  if (base === "/compliance/admin/w9-summary") {
    const total = Array.from(mockSignedByShoot.values()).reduce((s, l) => s + l.length, 0)
    let female = 0, male = 0
    for (const list of mockSignedByShoot.values()) {
      for (const s of list) {
        if (s.talent_role === "female") female++
        if (s.talent_role === "male") male++
      }
    }
    return wait({
      total,
      by_studio: total > 0
        ? { "VRHush": Math.floor(total / 2), "FuckPassVR": total - Math.floor(total / 2) }
        : {},
      by_role: { female, male },
      date_from: "",
      date_to: "",
      studio: "",
    } as unknown as T)
  }
  // GET /compliance/signatures/{id} — full row for the edit modal.
  // (Used by both the wizard's edit modal and the new Database view.)
  const sigGet = base.match(/^\/compliance\/signatures\/(\d+)$/)
  if (sigGet && (init?.method === undefined || init.method === "GET")) {
    const id = parseInt(sigGet[1], 10)
    const hit = MOCK_SIGNATURE_HITS.find(h => h.id === id)
    if (!hit) {
      throw new Error(`signature ${id} not found`)
    }
    return wait({
      ...hit,
      // Fields the SignatureRow has that the search hit doesn't:
      tax_classification: "individual",
      llc_class: "",
      other_classification: "",
      exempt_payee_code: "",
      fatca_code: "",
      tin: `XXX-XX-${hit.tin_last4}`,
      place_of_birth: "United States",
      street_address: "—",
      id1_type: "Driver's License",
      id1_number: "—",
      id2_type: "Passport",
      id2_number: "—",
      professional_names: hit.stage_names,
      created_at: hit.signed_at,
    } as unknown as T)
  }
  // GET /compliance/signatures/{id}/history — empty audit trail in dev
  const sigHist = base.match(/^\/compliance\/signatures\/(\d+)\/history$/)
  if (sigHist) {
    return wait([] as unknown as T)
  }

  // Searchable Compliance Database view (TKT-paperwork-db).
  if (base === "/compliance/admin/search") {
    const q = (params.get("q") ?? "").trim().toLowerCase()
    const dateFrom = params.get("from") ?? ""
    const dateTo   = params.get("to") ?? ""
    const studio   = params.get("studio") ?? ""
    const role     = params.get("role") ?? ""
    const limit    = Math.max(1, Math.min(1000, parseInt(params.get("limit") ?? "200", 10) || 200))
    const offset   = Math.max(0, parseInt(params.get("offset") ?? "0", 10) || 0)

    const tokens = q ? q.split(/\s+/).filter(Boolean) : []
    const matchToken = (h: typeof MOCK_SIGNATURE_HITS[number], tok: string): boolean => {
      const hay = [
        h.talent_display, h.legal_name, h.business_name,
        h.stage_names, h.nicknames_aliases, h.previous_legal_names,
        h.email, h.phone, h.city_state_zip,
        h.scene_id, h.shoot_id, h.studio, h.talent_slug,
      ].join(" ").toLowerCase()
      return hay.includes(tok)
    }

    let list = MOCK_SIGNATURE_HITS.filter(h => {
      if (dateFrom && h.shoot_date < dateFrom) return false
      if (dateTo   && h.shoot_date > dateTo)   return false
      if (studio   && h.studio !== studio)     return false
      if (role     && h.talent_role !== role)  return false
      for (const tok of tokens) if (!matchToken(h, tok)) return false
      return true
    })
    list = [...list].sort((a, b) =>
      (a.shoot_date < b.shoot_date) ? 1 :
      (a.shoot_date > b.shoot_date) ? -1 :
      (a.signed_at < b.signed_at) ? 1 :
      (a.signed_at > b.signed_at) ? -1 : 0
    )
    const total = list.length
    const hits = list.slice(offset, offset + limit)
    return wait({
      hits, total, limit, offset,
      query: q, date_from: dateFrom, date_to: dateTo, studio, role,
    } as unknown as T)
  }

  // MEGA legal-folder scanner.
  if (base === "/compliance/admin/legal-folders") {
    const studio = params.get("studio") ?? ""
    let files: ReadonlyArray<typeof MOCK_MEGA_LEGAL_FILES[number]> = MOCK_MEGA_LEGAL_FILES
    if (studio) files = files.filter(f => f.studio.toLowerCase() === studio.toLowerCase())
    return wait({
      files,
      scanned_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
      studios_scanned: studio ? [studio.toUpperCase()] : ["FPVR", "VRH", "VRA", "NJOI"],
      total: files.length,
      truncated: false,
    } as unknown as T)
  }
  // Bulk-import MEGA legal-folder PDFs (mock summary)
  if (base === "/compliance/admin/import-from-mega-legal" && init?.method === "POST") {
    const seen = MOCK_MEGA_LEGAL_FILES.length
    const imported = Math.max(0, seen - 2)
    return wait({
      shoots_seen: seen,
      shoots_processed: seen - 1,
      total_imported: imported,
      shoots: MOCK_MEGA_LEGAL_FILES.slice(0, 4).map(f => ({
        shoot_id: `mock-${f.scene_id}`,
        shoot_date: (f.last_modified || "").slice(0, 10) || "2026-01-01",
        scene_id: f.scene_id,
        studio: f.studio,
        talents_imported: 1,
        talents_skipped: 0,
        skipped_reason: "",
      })),
      errors: [],
    } as unknown as T)
  }

  if (base === "/compliance/admin/legal-folders/presign") {
    const studio = params.get("studio") ?? ""
    const key    = params.get("key") ?? ""
    return wait({
      url: `https://example.s4.mega.io/${studio.toLowerCase()}/${encodeURI(key)}?mock=1`,
      studio: studio.toUpperCase(),
      key,
    } as unknown as T)
  }

  // Rename a MEGA legal file. Mock just echoes the new key — the real
  // backend does COPY → DELETE on the bucket and rewrites the index.
  if (base === "/compliance/admin/legal-files/rename" && init?.method === "POST") {
    const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as {
      studio?: string; src_key?: string; new_filename?: string
    }
    const src_key = body.src_key ?? ""
    const new_filename = body.new_filename ?? ""
    const new_key = src_key.includes("/")
      ? src_key.replace(/[^/]+$/, new_filename)
      : new_filename
    return wait({
      ok: true,
      new_key,
      signatures_updated: 0,
    } as unknown as T)
  }

  // Rename a MEGA legal-folder prefix. Mock builds plausible plan rows
  // by listing the fixture MEGA files that share the src_prefix.
  if (base === "/compliance/admin/legal-folders/rename" && init?.method === "POST") {
    const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as {
      studio?: string; src_prefix?: string; dst_prefix?: string; dry_run?: boolean
    }
    const studio = (body.studio ?? "").toUpperCase()
    const src = body.src_prefix ?? ""
    const dst = body.dst_prefix ?? ""
    const matches = MOCK_MEGA_LEGAL_FILES
      .filter(f => f.studio === studio && f.key.startsWith(src))
      .map(f => ({ src: f.key, dst: dst + f.key.slice(src.length) }))
    return wait({
      ok: true,
      moved: body.dry_run ? 0 : matches.length,
      planned: matches,
      errors: [],
      conflict_count: 0,
      signatures_updated: 0,
      dry_run: !!body.dry_run,
    } as unknown as T)
  }

  if (base === "/compliance/admin/bulk-import-from-drive" && init?.method === "POST") {
    return wait({
      folders_seen: 18,
      folders_matched: 12,
      shoots: MOCK_COMPLIANCE_SHOOTS.slice(0, 2).map((s, i) => ({
        shoot_id: s.shoot_id,
        shoot_date: s.shoot_date,
        folder_name: `${s.shoot_date.replace(/-/g, "").slice(2,8)}-${s.female_talent.replace(/ /g, "")}-${s.male_talent.replace(/ /g, "")}`,
        talents_imported: i + 1,
        skipped_reason: "",
      })),
      errors: [],
    } as unknown as T)
  }

  // ── Compliance ────────────────────────────────────────────────────────
  if (base.startsWith("/compliance/shoots")) {
    // List shoots for a date, optionally filtered by name search.
    // Mirrors the real backend so the UI's empty-state and search affordances
    // can be exercised end-to-end against fixtures.
    if (base === "/compliance/shoots" || base === "/compliance/shoots/") {
      const dateParam = params.get("date")
      const q = (params.get("q") ?? "").trim().toLowerCase()
      let list = MOCK_COMPLIANCE_SHOOTS
      if (q) {
        list = list.filter(s =>
          s.female_talent.toLowerCase().includes(q) ||
          s.male_talent.toLowerCase().includes(q),
        )
      } else if (dateParam) {
        list = list.filter(s => s.shoot_date === dateParam)
      }
      return wait(list as unknown as T)
    }
    // Prepare
    const prepareMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/prepare$/)
    if (prepareMatch) {
      const shoot = MOCK_COMPLIANCE_SHOOTS.find(s => s.shoot_id === prepareMatch[1]) ?? MOCK_COMPLIANCE_SHOOTS[0]
      return wait({
        folder_id: shoot.drive_folder_id ?? "mock-folder-new",
        folder_url: shoot.drive_folder_url ?? "https://drive.google.com/drive/folders/mock-new",
        folder_name: shoot.drive_folder_name ?? `mock-${shoot.shoot_date}`,
        female_pdf_id: "mock-pdf-female",
        male_pdf_id: "mock-pdf-male",
        male_known: shoot.male_talent in { MikeMancini: 1, JaydenMarcos: 1, DannySteele: 1 },
        dates_filled: true,
        message: `${shoot.female_talent} PDF ready; ${shoot.male_talent} PDF + dates ready`,
      } as unknown as T)
    }
    // Photos upload
    const photosMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/photos$/)
    if (photosMatch) {
      return wait({
        uploaded: ["id-front.jpg", "id-back.jpg", "bunny-ear.jpg"],
        drive_file_ids: ["mock-id-1", "mock-id-2", "mock-id-3"],
        mega_paths: [],
        errors: [],
      } as unknown as T)
    }
    // Mega sync
    const megaMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/mega-sync$/)
    if (megaMatch) {
      return wait({
        status: "ok",
        mega_path: "mega:/Grail/FPVR/FPVR1337/Legal/",
        files_copied: 5,
        message: "Copied 5 files to MEGA",
      } as unknown as T)
    }
    // Fill form
    const fillMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/fill-form$/)
    if (fillMatch) {
      const shoot = MOCK_COMPLIANCE_SHOOTS.find(s => s.shoot_id === fillMatch[1]) ?? MOCK_COMPLIANCE_SHOOTS[0]
      return wait({
        folder_id: "mock-folder-id",
        folder_url: "https://drive.google.com/drive/folders/mock",
        folder_name: shoot.drive_folder_name ?? "mock-folder",
        female_pdf_id: "mock-female-pdf",
        male_pdf_id: "",
        male_known: false,
        dates_filled: true,
        message: "PDF saved to Drive",
      } as unknown as T)
    }
    // New TKT-0150 sign endpoint
    const signMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/sign$/)
    if (signMatch) {
      const shoot = MOCK_COMPLIANCE_SHOOTS.find(s => s.shoot_id === signMatch[1]) ?? MOCK_COMPLIANCE_SHOOTS[0]
      const body = (init?.body ? JSON.parse(init.body as string) : {}) as Record<string, unknown>
      const role = (body.talent_role as string) || "female"
      const slug = (body.talent_slug as string) || "MockTalent"
      const display = (body.talent_display as string) || (role === "female" ? shoot.female_talent : shoot.male_talent)
      const legalName = (body.legal_name as string) || display
      const signedAt = new Date().toISOString()
      const pdfMega = `mega:/Grail/${shoot.studio || "VRH"}/${shoot.scene_id || "MOCK"}/Legal/${slug}-${shoot.shoot_date}.pdf`
      // Store this signature on the shoot so /signed reflects it on next call
      const list = mockSignedByShoot.get(shoot.shoot_id) ?? []
      const filtered = list.filter(s => s.talent_role !== role)
      filtered.push({
        talent_role: role,
        talent_slug: slug,
        talent_display: display,
        legal_name: legalName,
        signed_at: signedAt,
        pdf_mega_path: pdfMega,
      })
      mockSignedByShoot.set(shoot.shoot_id, filtered)
      return wait({
        shoot_id: shoot.shoot_id,
        talent_role: role,
        talent_slug: slug,
        signed_at: signedAt,
        pdf_local_path: `/tmp/mock/${shoot.shoot_date}-${slug}.pdf`,
        pdf_mega_path: pdfMega,
        contract_version: "eclatech.v1.dev-mock",
      } as unknown as T)
    }
    // New TKT-0150 signed-summary endpoint
    const signedMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/signed$/)
    if (signedMatch) {
      const list = mockSignedByShoot.get(signedMatch[1]) ?? []
      return wait(list as unknown as T)
    }

    // ── TKT-0151 server-persisted photos ─────────────────────────────────
    // GET /compliance/shoots/{id}/photos-v2
    const listPhotosMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/photos-v2$/)
    if (listPhotosMatch && (init?.method ?? "GET") === "GET") {
      const list = mockPhotosByShoot.get(listPhotosMatch[1]) ?? []
      return wait(list as unknown as T)
    }
    // POST /compliance/shoots/{id}/photos-v2 — multipart body, parse FormData
    if (listPhotosMatch && init?.method === "POST") {
      const fd = init.body as FormData
      const file    = fd.get("file") as File | null
      const slotId  = (fd.get("slot_id") as string) || "slot"
      const label   = (fd.get("label") as string) || (file?.name ?? "photo.jpg")
      const role    = (fd.get("talent_role") as string) || ""
      const url     = file ? URL.createObjectURL(file) : ""
      const photo: MockPhoto = {
        slot_id: slotId,
        talent_role: role,
        label,
        mime_type: file?.type || "image/jpeg",
        file_size: file?.size || 0,
        uploaded_at: new Date().toISOString(),
        mega_path: `mega:/Grail/MOCK/MOCK0001/Legal/${label}`,
        url,
      }
      const list = mockPhotosByShoot.get(listPhotosMatch[1]) ?? []
      const filtered = list.filter(p => p.slot_id !== slotId)
      filtered.push(photo)
      mockPhotosByShoot.set(listPhotosMatch[1], filtered)
      return wait(photo as unknown as T)
    }
    // DELETE /compliance/shoots/{id}/photos-v2/{slot_id}
    const delPhotoMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/photos-v2\/(.+)$/)
    if (delPhotoMatch && init?.method === "DELETE") {
      const list = mockPhotosByShoot.get(delPhotoMatch[1]) ?? []
      mockPhotosByShoot.set(delPhotoMatch[1], list.filter(p => p.slot_id !== decodeURIComponent(delPhotoMatch[2])))
      return wait({ ok: true } as unknown as T)
    }
    // GET (single photo bytes) — dev mock returns null; UI uses blob url instead
    if (delPhotoMatch && (init?.method ?? "GET") === "GET") {
      return wait(null as unknown as T, 30)
    }

    // ── TKT-0152 import-from-drive ───────────────────────────────────────
    const importMatch = base.match(/^\/compliance\/shoots\/([^/]+)\/import-from-drive$/)
    if (importMatch && init?.method === "POST") {
      const sid = importMatch[1]
      const shoot = MOCK_COMPLIANCE_SHOOTS.find(s => s.shoot_id === sid) ?? MOCK_COMPLIANCE_SHOOTS[0]
      const list = mockSignedByShoot.get(shoot.shoot_id) ?? []
      const now = new Date().toISOString()
      const slugs = [
        ["female", shoot.female_talent.replace(/ /g, ""), shoot.female_talent],
        ...(shoot.male_talent ? [["male", shoot.male_talent.replace(/ /g, ""), shoot.male_talent] as const] : []),
      ] as const
      const imported = slugs.map(([role, slug, display]) => {
        const filtered = list.filter(s => s.talent_role !== role)
        filtered.push({
          talent_role: role,
          talent_slug: slug,
          talent_display: display,
          legal_name: display,
          signed_at: now,
          pdf_mega_path: `mega:/Grail/${shoot.studio || "MOCK"}/${shoot.scene_id || "MOCK"}/Legal/${slug}-mock.pdf`,
        })
        list.length = 0
        list.push(...filtered)
        return { talent_role: role, talent_slug: slug, pdf_local_path: `/mock/${slug}.pdf`, pdf_mega_path: `mega:/Grail/MOCK/MOCK0001/Legal/${slug}.pdf`, bytes_copied: 123456 }
      })
      mockSignedByShoot.set(shoot.shoot_id, list)
      return wait({
        shoot_id: shoot.shoot_id,
        imported,
        skipped: [],
        errors: [],
      } as unknown as T)
    }
  }

  // ── Uploads ────────────────────────────────────────────────────────────
  // Dev mock simulates the FastAPI broker — but presigned URLs point at
  // /__dev_upload_sink so the orchestrator's PUT loop stays exercised
  // without hitting MEGA. The sink is a Next.js route that returns 200 +
  // a fake ETag.
  if (base === "/uploads/head") {
    return wait({ exists: false } as unknown as T)
  }
  if (base === "/uploads/multipart/init" && init?.method === "POST") {
    const body = init.body ? JSON.parse(init.body as string) : {}
    const partSize = 64 * 1024 * 1024
    const partCount = Math.max(1, Math.ceil((body.size ?? 0) / partSize))
    const sceneId = body.scene_id ?? "DEV0001"
    const subfolder = body.subfolder ?? "Description"
    const filename = body.filename ?? "file.bin"
    return wait({
      upload_id: `dev-mock-${Date.now()}`,
      bucket: `dev-${(body.studio ?? "vrh").toLowerCase()}`,
      key: `${sceneId}/${subfolder}/${filename}`,
      part_size: partSize,
      part_count: partCount,
    } as unknown as T)
  }
  if (base === "/uploads/multipart/sign-parts" && init?.method === "POST") {
    const body = init.body ? JSON.parse(init.body as string) : {}
    const urls = (body.part_numbers ?? []).map((n: number) => ({
      part_number: n,
      url: `/__dev_upload_sink?upload_id=${encodeURIComponent(body.upload_id ?? "")}&part=${n}`,
    }))
    return wait({ urls } as unknown as T)
  }
  if (base === "/uploads/multipart/complete" && init?.method === "POST") {
    const body = init.body ? JSON.parse(init.body as string) : {}
    return wait({
      ok: true,
      bucket: `dev-${(body.studio ?? "vrh").toLowerCase()}`,
      key: body.key ?? "DEV0001/Description/file.bin",
      etag: "mock-final-etag",
      presigned_url: `https://dev-mock.example/${encodeURIComponent(body.key ?? "")}`,
    } as unknown as T)
  }
  if (base === "/uploads/multipart/abort" && init?.method === "POST") {
    return wait({ ok: true, aborted_lingering: 0 } as unknown as T)
  }
  if (base === "/uploads/history") {
    return wait([
      {
        ts: Date.now() / 1000 - 120,
        user_email: "drew@eclatech.studio",
        user_name: "Drew",
        studio: "VRH",
        scene_id: "VRH0762",
        subfolder: "Videos",
        filename: "VRH0762_Final.mp4",
        key: "VRH0762/Videos/VRH0762_Final.mp4",
        size: 2_800_000_000,
        mode: "direct",
      },
      {
        ts: Date.now() / 1000 - 14 * 60,
        user_email: "david@eclatech.studio",
        user_name: "David",
        studio: "FPVR",
        scene_id: "FPVR0010",
        subfolder: "Description",
        filename: "FPVR0010-MayThai-JasonX.docx",
        key: "FPVR0010/Description/FPVR0010-MayThai-JasonX.docx",
        size: 42_000,
        mode: "direct",
      },
    ] as unknown as T)
  }

  // ── Revenue (Premium Breakdowns) ───────────────────────────────────────
  // Numbers below mirror real-shape values so layouts stay honest in dev.
  if (base === "/revenue/dashboard") {
    return wait({
      grand_total: 2_500_914.76,
      ytd_total:   168_350.29,
      refreshed_at: new Date().toISOString(),
      platforms: [
        { platform: "slr",    all_time: 1_951_027.08, ytd: 74_571.85,
          yearly: { "2018": 8100.20, "2019": 35_330.62, "2020": 125_769.87, "2021": 217_076.22, "2022": 350_718.98, "2023": 356_442.80, "2024": 404_902.80, "2025": 378_113.74, "2026": 74_571.85 } },
        { platform: "povr",   all_time: 374_145.23, ytd: 27_771.61,
          yearly: { "2022": 11_685.21, "2023": 52_409.15, "2024": 134_289.48, "2025": 147_989.78, "2026": 27_771.61 } },
        { platform: "vrporn", all_time: 175_742.45, ytd: 66_006.83,
          yearly: { "2025": 109_735.62, "2026": 66_006.83 } },
      ],
      monthly_trend: [
        { month: "2025-06", slr: 28_291.20, povr: 12_950.24, vrporn: 0,         total: 41_241.44, mom_pct: null },
        { month: "2025-07", slr: 28_465.01, povr: 12_543.14, vrporn: 0,         total: 41_008.15, mom_pct: -0.6 },
        { month: "2025-08", slr: 30_568.77, povr: 12_256.40, vrporn: 0,         total: 42_825.17, mom_pct:  4.4 },
        { month: "2025-09", slr: 33_829.87, povr: 13_190.84, vrporn: 27_346.81, total: 74_367.52, mom_pct: 73.7 },
        { month: "2025-10", slr: 33_057.25, povr: 13_759.47, vrporn: 25_768.73, total: 72_585.45, mom_pct: -2.4 },
        { month: "2025-11", slr: 30_092.07, povr: 12_942.92, vrporn: 26_402.47, total: 69_437.46, mom_pct: -4.3 },
        { month: "2025-12", slr: 31_567.58, povr: 12_682.56, vrporn: 30_217.61, total: 74_467.75, mom_pct:  7.2 },
        { month: "2026-01", slr: 31_246.19, povr: 10_979.46, vrporn: 27_421.91, total: 69_647.56, mom_pct: -6.5 },
        { month: "2026-02", slr: 27_993.81, povr: 11_027.02, vrporn: 24_422.28, total: 63_443.11, mom_pct: -8.9 },
        { month: "2026-03", slr: 28_002.97, povr:  9_320.27, vrporn:  6_540.12, total: 43_863.36, mom_pct: -30.9 },
        // April + May synthesized from "_DailyData" rollups in the mock to
        // mirror how the API now backfills months missing from _Data.
        { month: "2026-04", slr:  2_644.28, povr: 10_649.20, vrporn: 11_724.84, total: 25_018.32, mom_pct: -43.0 },
        { month: "2026-05", slr:    421.00, povr:  1_507.80, vrporn:  1_932.45, total:  3_861.25, mom_pct: -84.6 },
      ],
      catalog: [
        { platform: "povr",   total_scenes: 4749, avg_revenue_per_scene:  78.91, top_scene_revenue: 1_220.78 },
        { platform: "slr",    total_scenes: 1688, avg_revenue_per_scene:   1.23, top_scene_revenue:   233.63 },
        { platform: "vrporn", total_scenes: 1638, avg_revenue_per_scene: 107.72, top_scene_revenue: 4_362.90 },
      ],
    } as unknown as T)
  }
  if (base === "/revenue/scenes") {
    return wait([
      { platform: "vrporn", studio: "VRH",  video_id: "octavia-red-companion",     title: "Watch and Play - Octavia Red",         year: "2025", views: 6534, revenue: 4_362.90 },
      { platform: "vrporn", studio: "FPVR", video_id: "can-you-make-it",            title: "Can you make it? - Aria Valencia",     year: "2025", views: 5103, revenue: 3_188.42 },
      { platform: "povr",   studio: "FPVR", video_id: "5715509",                    title: "Are You Recording Me? I'm Telling Mom!", year: "2024", views: 2001, revenue: 1_220.78 },
      { platform: "vrporn", studio: "VRH",  video_id: "from-the-vault-recording",   title: "From the Vault: Are You Recording Me? I'm Telling Mom!", year: "2021", views: 6232, revenue: 1_708.46 },
      { platform: "vrporn", studio: "VRH",  video_id: "rhythm-of-seduction",        title: "Rhythm of Seduction",                  year: "2025", views: 5183, revenue: 1_385.92 },
      { platform: "vrporn", studio: "VRH",  video_id: "love-is-in-the-heir-tonight",title: "Love Is in the Heir Tonight",          year: "2025", views: 4934, revenue: 1_459.69 },
      { platform: "vrporn", studio: "VRA",  video_id: "the-emergency-pleasure",     title: "The Emergency Pleasure Patch",         year: "2025", views: 4476, revenue: 1_240.82 },
      { platform: "slr",    studio: "FPVR", video_id: "80880",                      title: "(80880) Reserved For Your Hands",      year: "2026", views: 2854, revenue:   233.63 },
      { platform: "slr",    studio: "VRH",  video_id: "81564",                      title: "(81564) Artists in Love",              year: "2026", views: 1770, revenue:   114.29 },
      { platform: "povr",   studio: "FPVR", video_id: "5769247",                    title: "Lifetime hit",                         year: "2024", views: 5637, revenue:   980.76 },
    ] as unknown as T)
  }
  if (base === "/revenue/cross-platform") {
    return wait([
      { title: "From the Vault: Are You Recording Me? I'm Telling Mom!", studio: "VRH", platforms: ["POVR","SLR","VRPorn"], lifetime_total: 2_692.62, slr_total: 3.40,  povr_total:   980.76, vrporn_total: 1_708.46, povr_views: 5637, slr_id: "23600",   povr_id: "5769247" },
      { title: "Are You Recording Me? I'm Telling Mom!",                  studio: "VRH", platforms: ["POVR","VRPorn"],       lifetime_total: 2_097.62, slr_total: 0,     povr_total:   389.16, vrporn_total: 1_708.46, povr_views: 2001, slr_id: "",        povr_id: "5715509" },
      { title: "Watch and Play - Octavia Red",                            studio: "VRH", platforms: ["POVR","VRPorn"],       lifetime_total: 4_582.10, slr_total: 0,     povr_total:   219.20, vrporn_total: 4_362.90, povr_views:  410, slr_id: "",        povr_id: "5821111" },
    ] as unknown as T)
  }
  if (base === "/revenue/daily") {
    // Multi-platform daily rows ending yesterday — mirrors the production
    // _DailyData state where POVR + SLR + VRPorn all push daily totals.
    const today = new Date()
    today.setUTCHours(0, 0, 0, 0)
    const rows: { date: string; platform: string; studio: string; revenue: number }[] = []
    for (let i = 25; i >= 1; i--) {
      const d = new Date(today.getTime() - i * 86_400_000)
      const iso = d.toISOString().slice(0, 10)
      const hash = [...iso].reduce((a, c) => a + c.charCodeAt(0), 0)
      // Each platform contributes a stable pseudo-random amount per day.
      rows.push({ date: iso, platform: "vrporn", studio: "All", revenue: 450 + (hash % 350) })
      rows.push({ date: iso, platform: "povr",   studio: "All", revenue: 280 + (hash % 220) })
      rows.push({ date: iso, platform: "slr",    studio: "VRH", revenue: 180 + (hash % 140) })
    }
    const yesterdayDate = rows[rows.length - 1].date
    const yesterdayRows = rows.filter(r => r.date === yesterdayDate)
    const yesterdayTotal = yesterdayRows.reduce((acc, r) => acc + r.revenue, 0)
    const monthPrefix = yesterdayDate.slice(0, 7)
    const monthRows = rows.filter(r => r.date.startsWith(monthPrefix))
    const monthTotal = monthRows.reduce((acc, r) => acc + r.revenue, 0)
    return wait({
      yesterday: yesterdayRows,
      yesterday_date: yesterdayDate,
      yesterday_total: Math.round(yesterdayTotal * 100) / 100,
      this_month: monthRows,
      this_month_total: Math.round(monthTotal * 100) / 100,
      refreshed_at: new Date().toISOString(),
    } as unknown as T)
  }
  if (base === "/revenue/scene/lookup") {
    return wait([
      { platform: "slr",    studio: "VRH",  video_id: "23600",   title: "From the Vault: Are You Recording Me?", year: "2021", views: 102, revenue: 3.40 },
      { platform: "povr",   studio: "FPVR", video_id: "5769247", title: "Are You Recording Me?",                 year: "2024", views: 5637, revenue: 980.76 },
      { platform: "vrporn", studio: "VRH",  video_id: "from-the-vault-recording", title: "From the Vault",       year: "2021", views: 6232, revenue: 1_708.46 },
    ] as unknown as T)
  }

  // eslint-disable-next-line no-console
  console.warn(`[dev-mock-api] Unmapped path: ${path}`)
  return wait(null as unknown as T, 60)
}
