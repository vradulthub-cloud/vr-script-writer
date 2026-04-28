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
  MOCK_COMPLIANCE_SHOOTS,
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
    // List shoots for a date
    if (base === "/compliance/shoots" || base === "/compliance/shoots/") {
      return wait(MOCK_COMPLIANCE_SHOOTS as unknown as T)
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

  // eslint-disable-next-line no-console
  console.warn(`[dev-mock-api] Unmapped path: ${path}`)
  return wait(null as unknown as T, 60)
}
