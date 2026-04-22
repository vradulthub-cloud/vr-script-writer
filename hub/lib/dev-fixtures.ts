/**
 * Dev-only mock data for testing the UI without the FastAPI backend.
 *
 * This module is ONLY consumed when NODE_ENV !== "production" AND
 * process.env.DEV_AUTH_MOCK === "1" (server) or
 * process.env.NEXT_PUBLIC_DEV_AUTH_MOCK === "1" (client). Production
 * bundles never read these fixtures because the guards live behind a
 * `process.env.NODE_ENV === "production"` short-circuit.
 */

import type {
  Approval,
  Notification,
  Scene,
  SceneStats,
  Script,
  Ticket,
  TicketStats,
  UserProfile,
  Model,
  ShootDate,
} from "./api"

interface Health {
  status: string
  version: string
  syncs: Record<string, unknown>
}

export const DEV_MOCK_ENABLED =
  process.env.NODE_ENV !== "production" &&
  (process.env.NEXT_PUBLIC_DEV_AUTH_MOCK === "1" ||
    process.env.DEV_AUTH_MOCK === "1")

export const MOCK_USER: UserProfile = {
  email: "dev@eclatech.test",
  name: "Dev Admin",
  role: "admin",
  allowed_tabs: "ALL",
}

export const MOCK_ALL_USERS: UserProfile[] = [
  MOCK_USER,
  { email: "editor1@eclatech.test",  name: "Editor One",  role: "editor", allowed_tabs: "Tickets,Scripts,Descriptions" },
  { email: "editor2@eclatech.test",  name: "Editor Two",  role: "editor", allowed_tabs: "Tickets,Descriptions,Titles" },
  { email: "editor3@eclatech.test",  name: "Editor Three",role: "editor", allowed_tabs: "Tickets" },
]

export const MOCK_SCENE_STATS: SceneStats = {
  total: 1274,
  by_studio: {
    FuckPassVR: 482,
    VRHush:     356,
    VRAllure:   291,
    NaughtyJOI: 145,
  },
  complete: 1157,
  missing_any: 117,
}

export const MOCK_APPROVALS: Approval[] = [
  {
    approval_id: "APR-0001",
    scene_id: "FPVR-1204",
    studio: "FuckPassVR",
    content_type: "description",
    submitted_by: "editor1@eclatech.test",
    submitted_at: "2026-04-16T14:22:00Z",
    status: "Pending",
    decided_by: "",
    decided_at: "",
    content_json: JSON.stringify({
      description: "A sun-drenched afternoon in Santorini takes a turn when Sofia finds the villa pool too inviting to resist. What starts as a casual dip becomes something far more intimate as she locks eyes with the caretaker across the terrace. Shot in stunning 8K VR with spatial audio that brings every whispered word close.",
      meta_title: "Sofia's Santorini Afternoon — 8K VR",
    }),
    notes: "",
    target_sheet: "FPVR",
    target_range: "F1204",
  },
  {
    approval_id: "APR-0002",
    scene_id: "VRH-0987",
    studio: "VRHush",
    content_type: "script",
    submitted_by: "editor2@eclatech.test",
    submitted_at: "2026-04-16T10:15:00Z",
    status: "Pending",
    decided_by: "",
    decided_at: "",
    content_json: JSON.stringify({
      theme: "Rainy evening, inherited apartment, unfinished painting",
      plot: "Jade discovers a half-finished self-portrait her late aunt left behind — and the model who was posing for it.",
    }),
    notes: "",
    target_sheet: "VRH",
    target_range: "G987",
  },
  {
    approval_id: "APR-0003",
    scene_id: "VRA-0410",
    studio: "VRAllure",
    content_type: "compilation",
    submitted_by: "editor1@eclatech.test",
    submitted_at: "2026-04-15T18:02:00Z",
    status: "Pending",
    decided_by: "",
    decided_at: "",
    content_json: JSON.stringify({
      title: "VRAllure Best of Q1",
      scene_ids: ["VRA-0392", "VRA-0401", "VRA-0406", "VRA-0410"],
    }),
    notes: "",
    target_sheet: "",
    target_range: "",
  },
]

function scene(opts: Partial<Scene> & Pick<Scene, "id" | "studio">): Scene {
  return {
    id: opts.id,
    studio: opts.studio,
    grail_tab: opts.grail_tab ?? "",
    site_code: opts.site_code ?? "",
    title: opts.title ?? "",
    performers: opts.performers ?? "",
    categories: opts.categories ?? "",
    tags: opts.tags ?? "",
    release_date: opts.release_date ?? "",
    female: opts.female ?? "",
    male: opts.male ?? "",
    plot: opts.plot ?? "",
    theme: opts.theme ?? "",
    is_compilation: opts.is_compilation ?? false,
    has_description: opts.has_description ?? false,
    has_videos: opts.has_videos ?? false,
    video_count: opts.video_count ?? 0,
    has_thumbnail: opts.has_thumbnail ?? false,
    has_photos: opts.has_photos ?? false,
    has_storyboard: opts.has_storyboard ?? false,
    storyboard_count: opts.storyboard_count ?? 0,
    mega_path: opts.mega_path ?? "",
    grail_row: opts.grail_row ?? 0,
  }
}

export const MOCK_SCENES: Scene[] = [
  scene({
    id: "FPVR-1204", studio: "FuckPassVR", grail_tab: "FPVR", site_code: "fpvr",
    title: "Sofia's Santorini Afternoon", performers: "Sofia Cruz / Mark Stone",
    female: "Sofia Cruz", male: "Mark Stone",
    release_date: "2026-04-12",
    plot: "A villa, a pool, a late afternoon sun. Two characters. One decision.",
    theme: "Mediterranean villa, golden hour",
    has_description: false, has_videos: true, video_count: 2,
    has_thumbnail: true, has_photos: false, has_storyboard: true,
    storyboard_count: 8,
    mega_path: "/Grail/FPVR/FPVR-1204",
    grail_row: 1204,
    categories: "Blowjob, Cowgirl, Big Tits",
    tags: "Travel, 8K VR, Brunette",
  }),
  scene({
    id: "FPVR-1203", studio: "FuckPassVR", grail_tab: "FPVR", site_code: "fpvr",
    title: "Rooftop Heat", performers: "Ava Brooks / James Deen",
    release_date: "2026-04-08",
    has_description: true, has_videos: true, video_count: 2,
    has_thumbnail: true, has_photos: true, has_storyboard: false,
    mega_path: "/Grail/FPVR/FPVR-1203",
  }),
  scene({
    id: "FPVR-1202", studio: "FuckPassVR", grail_tab: "FPVR", site_code: "fpvr",
    title: "Late Check-In", performers: "Luna Star / Ryan Grey",
    release_date: "2026-04-05",
    has_description: true, has_videos: false, video_count: 0,
    has_thumbnail: false, has_photos: true, has_storyboard: true,
    storyboard_count: 6,
  }),
  scene({
    id: "VRH-0988", studio: "VRHush", grail_tab: "VRH", site_code: "vrh",
    title: "Inheritance", performers: "Jade Lane / Daniel Cole",
    release_date: "2026-04-14",
    has_description: true, has_videos: false, video_count: 0,
    has_thumbnail: true, has_photos: true, has_storyboard: true,
    storyboard_count: 7,
    mega_path: "/Grail/VRH/VRH-0988",
  }),
  scene({
    id: "VRH-0987", studio: "VRHush", grail_tab: "VRH", site_code: "vrh",
    title: "The Painter", performers: "Jade Lane / Daniel Cole",
    release_date: "2026-04-10",
    has_description: false, has_videos: true, video_count: 1,
    has_thumbnail: true, has_photos: false, has_storyboard: false,
    mega_path: "/Grail/VRH/VRH-0987",
  }),
  // Regression fixture: has_thumbnail flag is stale (sync set it true)
  // but mega_path is empty. Retry UI would always fail here — should show
  // "None" instead. Matches the real-world VRH0763 state.
  scene({
    id: "VRH-0986", studio: "VRHush", grail_tab: "VRH", site_code: "vrh",
    title: "Blurred Lines of Desire", performers: "Serena Hill / Mike Mancini",
    release_date: "2026-04-09",
    has_description: true, has_videos: false, video_count: 0,
    has_thumbnail: true, has_photos: false, has_storyboard: false,
    mega_path: "",
  }),
  scene({
    id: "VRA-0412", studio: "VRAllure", grail_tab: "VRA", site_code: "vra",
    title: "Private Collection", performers: "Nina Rivers",
    release_date: "2026-04-13",
    has_description: true, has_videos: true, video_count: 1,
    has_thumbnail: false, has_photos: false, has_storyboard: true,
    storyboard_count: 4,
  }),
  scene({
    id: "VRA-0411", studio: "VRAllure", grail_tab: "VRA", site_code: "vra",
    title: "Lace & Lacquer", performers: "Maya Knox",
    release_date: "2026-04-09",
    has_description: true, has_videos: true, video_count: 1,
    has_thumbnail: true, has_photos: true, has_storyboard: true,
    storyboard_count: 5,
    mega_path: "/Grail/VRA/VRA-0411",
  }),
  scene({
    id: "NJOI-0310", studio: "NaughtyJOI", grail_tab: "NNJOI", site_code: "njoi",
    title: "Countdown Tuesday", performers: "Harper Lane",
    release_date: "2026-04-11",
    has_description: false, has_videos: false, video_count: 0,
    has_thumbnail: false, has_photos: false, has_storyboard: false,
  }),
]

export const MOCK_SCRIPTS: Script[] = [
  {
    id: 1, tab_name: "FPVR - May", sheet_row: 12,
    studio: "FuckPassVR", shoot_date: "2026-05-03",
    female: "Sofia Cruz", male: "Mark Stone",
    theme: "", plot: "", title: "", script_status: "needs_script",
  },
  {
    id: 2, tab_name: "VRH - May", sheet_row: 7,
    studio: "VRHush", shoot_date: "2026-05-06",
    female: "Jade Lane", male: "Daniel Cole",
    theme: "", plot: "", title: "", script_status: "needs_script",
  },
  // Populated scripts that match the shoots on 2026-04-16 and 2026-04-20 —
  // lets the ShootModal's Script section render real theme/plot content in
  // dev-mock mode. Real prod scripts come from the backing Sheet.
  {
    id: 3, tab_name: "VRH - Apr", sheet_row: 4,
    studio: "VRHush", shoot_date: "2026-04-16",
    female: "Harley Love", male: "Mike Mancini",
    theme: "Rainy afternoon — apartment alone, the boyfriend's roommate gets locked out on the balcony.",
    plot: "Harley is home studying when Mike knocks on the balcony door soaked from the rain. She lets him in, hands him a towel, and realizes he's her boyfriend's new roommate. The tension builds as he changes in the living room; she pretends not to look. One glance too long and they're both committed. Cut to morning — she's in his hoodie, texting the boyfriend that she 'made it home safe'.",
    title: "Harley Unbound",
    script_status: "validated",
    wardrobe_f: "Oversized college hoodie (grey), cotton shorts, simple gold hoops, no makeup except tinted lip.",
    wardrobe_m: "Wet white t-shirt (soaked through), dark wash jeans, one rain-soaked canvas jacket to hand over.",
    shoot_location: "Studio B — apartment set, balcony rig, rain loop running off-camera.",
    props: "Hardcover textbook (open), laptop, two mugs, kitchen towel, oversized men's hoodie for the Act III beat.",
  },
  {
    id: 4, tab_name: "VRA - Apr", sheet_row: 8,
    studio: "VRAllure", shoot_date: "2026-04-16",
    female: "Harley Love", male: "",
    theme: "Solo spotlight — Harley unwinds after a long shoot, talking directly to the viewer.",
    plot: "Soft golden-hour lighting through sheer curtains. Harley speaks quietly to the camera, explaining how the day went. She loosens her jewelry one piece at a time, pausing between each. The pacing is deliberate — no rush, no cut-aways. Ends on a close whispered 'goodnight' that breaks the fourth wall on purpose.",
    title: "Low Light",
    script_status: "validated",
    wardrobe_f: "Vintage slip dress (champagne), layered fine gold chains, small hoop earrings, barefoot.",
    shoot_location: "Studio B — small bedroom set, sheer curtains, warm practical lamp only.",
    props: "Hairbrush, small jewelry tray, glass of white wine (hero glass + stand-in).",
  },
  {
    id: 5, tab_name: "FPVR - Apr", sheet_row: 9,
    studio: "FuckPassVR", shoot_date: "2026-04-20",
    female: "Sophia Locke", male: "",
    theme: "Locked out of her own house, Sophia waits for the locksmith — passes the time with the viewer.",
    plot: "Sophia is sitting on the front porch in a sundress, locksmith is 45 minutes late. She decides to make the wait entertaining. Playful, knowing energy — aware she's being watched. Several costume adjustments that are very clearly for the camera's benefit. Breaks when the locksmith's van pulls into the drive.",
    title: "Front Porch",
    script_status: "validated",
    wardrobe_f: "Yellow floral sundress (no bra), nude strappy sandals, small pendant necklace, sunglasses pushed up.",
    shoot_location: "David's house — front porch, afternoon sun, neighborhood ambient.",
    props: "Phone (hero), house keys (rattling), small tote bag, takeaway iced coffee cup.",
  },
  {
    id: 6, tab_name: "NNJOI - Apr", sheet_row: 5,
    studio: "NaughtyJOI", shoot_date: "2026-04-20",
    female: "Sophia Locke", male: "",
    theme: "Late-night JOI — Sophia can't sleep, decides to help the viewer settle in too.",
    plot: "Dim bedroom, one bedside lamp. Sophia sits cross-legged on the bed holding a glass of red wine. Her instructions are slow and conversational — matches the viewer's breathing, then guides the pace up steadily. Ends with the lamp clicking off and a whispered 'sweet dreams'.",
    title: "Wine & Wind Down",
    script_status: "validated",
    wardrobe_f: "Black silk cami + matching shorts, thin silver anklet, hair down and slightly messy.",
    shoot_location: "David's house — primary bedroom, one practical bedside lamp, blackout outside.",
    props: "Stemmed red-wine glass, half-full decanter, open paperback on nightstand.",
  },
]

export const MOCK_NOTIFICATIONS: Notification[] = [
  {
    notif_id: "N-0012", timestamp: "2026-04-16T18:02:00Z",
    recipient: "dev@eclatech.test", type: "approval_submitted",
    title: "New approval: VRA-0410 compilation",
    message: "editor1@eclatech.test submitted a VRAllure compilation plan for your review",
    read: 0, link: "/approvals",
  },
  {
    notif_id: "N-0011", timestamp: "2026-04-16T14:22:00Z",
    recipient: "dev@eclatech.test", type: "approval_submitted",
    title: "New approval: FPVR-1204 description",
    message: "SEO description for Sofia's Santorini Afternoon needs your review",
    read: 0, link: "/approvals",
  },
  {
    notif_id: "N-0010", timestamp: "2026-04-16T12:08:00Z",
    recipient: "dev@eclatech.test", type: "ticket_created",
    title: "TKT-0046 created",
    message: "hub: SceneDetail never renders the scene thumbnail",
    read: 0, link: "/tickets",
  },
  {
    notif_id: "N-0009", timestamp: "2026-04-15T22:41:00Z",
    recipient: "dev@eclatech.test", type: "ticket_status",
    title: "TKT-0045 moved to In Review",
    message: "hub: final polish — dead CSS, mono token, notification clamp",
    read: 1, link: "/tickets",
  },
  {
    notif_id: "N-0008", timestamp: "2026-04-15T18:02:00Z",
    recipient: "dev@eclatech.test", type: "approval_decided",
    title: "Approved: VRH-0985 description",
    message: "",
    read: 1, link: "/approvals",
  },
]

export const MOCK_HEALTH: Health = {
  status: "ok",
  version: "2026.04.16-dev",
  syncs: {
    scenes:  { last_synced_at: "2026-04-16T18:00:00Z", row_count: 1274, status: "ok" },
    scripts: { last_synced_at: "2026-04-16T17:55:00Z", row_count: 186,  status: "ok" },
    models:  { last_synced_at: "2026-04-16T17:45:00Z", row_count: 412,  status: "ok" },
    budget:  { last_synced_at: "2026-04-16T17:30:00Z", row_count: 48,   status: "ok" },
  },
}

export const MOCK_TICKETS: Ticket[] = [
  {
    ticket_id: "TKT-0046", title: "hub: SceneDetail never renders the scene thumbnail",
    description: "Clicking a scene on the Asset Tracker opens SceneDetail but no thumbnail image is shown.",
    project: "Hub", type: "Bug", priority: "Medium", status: "Closed",
    submitted_by: "Drew (via Claude)", submitted_at: "2026-04-16T19:10:00Z",
    assignee: "", notes: "Merged in PR #10.", resolved_at: "2026-04-16T19:30:00Z",
    linked_items: "",
  },
  {
    ticket_id: "TKT-0045", title: "hub: final polish — dead CSS, mono token, notification clamp",
    description: "Minor-observations pass from /critique.",
    project: "Hub", type: "Improvement", priority: "Low", status: "Closed",
    submitted_by: "Claude (/polish)", submitted_at: "2026-04-16T18:45:00Z",
    assignee: "", notes: "Merged in PR #9.", resolved_at: "2026-04-16T18:50:00Z",
    linked_items: "",
  },
  {
    ticket_id: "TKT-0022", title: "hub: Script Generator mode switch silently destroys manual inputs",
    description: "Switching from manual to sheet mode clears the form without warning.",
    project: "Hub", type: "Bug", priority: "High", status: "In Review",
    submitted_by: "Drew", submitted_at: "2026-04-10T09:00:00Z",
    assignee: "dev@eclatech.test", notes: "", resolved_at: "",
    linked_items: "",
  },
  {
    ticket_id: "TKT-0019", title: "hub: filter persistence across page navigation",
    description: "Studio filter resets when leaving and returning to Asset Tracker.",
    project: "Hub", type: "Feature", priority: "Medium", status: "In Progress",
    submitted_by: "Editor One", submitted_at: "2026-04-08T14:30:00Z",
    assignee: "dev@eclatech.test", notes: "", resolved_at: "",
    linked_items: "",
  },
  // Content tickets with scene IDs — exercise the studio filter + Studio
  // column. Without these the per-studio chip counts all show 0 in dev.
  {
    ticket_id: "TKT-0033", title: "FPVR1284 — passport stamp missing on outro",
    description: "Final scene cuts before the passport stamp lands. Re-edit needed.",
    project: "Content", type: "Bug", priority: "Medium", status: "In Progress",
    submitted_by: "Editor Two", submitted_at: "2026-04-19T10:00:00Z",
    assignee: "dev@eclatech.test", notes: "", resolved_at: "",
    linked_items: "FPVR1284",
  },
  {
    ticket_id: "TKT-0034", title: "VRH0987 — title art is the wrong treatment",
    description: "We approved Treatment B but Treatment A shipped.",
    project: "Content", type: "Bug", priority: "High", status: "New",
    submitted_by: "Editor One", submitted_at: "2026-04-20T09:15:00Z",
    assignee: "", notes: "", resolved_at: "",
    linked_items: "VRH0987",
  },
  {
    ticket_id: "TKT-0035", title: "VRA0419 — meta description below 150 chars",
    description: "SEO check flagged the description as too short.",
    project: "Content", type: "Improvement", priority: "Low", status: "In Review",
    submitted_by: "Editor Three", submitted_at: "2026-04-19T16:42:00Z",
    assignee: "Editor Two", notes: "", resolved_at: "",
    linked_items: "VRA0419",
  },
  {
    ticket_id: "TKT-0036", title: "NJOI0042 — countdown audio drift after edit",
    description: "Voice and on-screen counter desync by ~200ms after the seven mark.",
    project: "Content", type: "Bug", priority: "High", status: "In Progress",
    submitted_by: "Editor Two", submitted_at: "2026-04-21T11:20:00Z",
    assignee: "dev@eclatech.test", notes: "", resolved_at: "",
    linked_items: "NJOI0042",
  },
  // ── Audit entries (synthetic tickets written by users-panel.tsx whenever
  //    a permission change is saved). The admin Audit Log panel filters on
  //    type=Audit so these surface there, not in the regular Tickets list.
  {
    ticket_id: "TKT-9007", title: "Admin change: editor3@eclatech.test — role editor → admin",
    description: "Changed by Drew at 2026-04-21T15:30:00Z.\n\nrole editor → admin",
    project: "Hub", type: "Audit", priority: "Low", status: "New",
    submitted_by: "Drew", submitted_at: "2026-04-21T15:30:00Z",
    assignee: "", notes: "", resolved_at: "", linked_items: "",
  },
  {
    ticket_id: "TKT-9006", title: "Admin change: contractor@eclatech.test — tabs ALL → Tickets, Scripts",
    description: "Changed by Drew at 2026-04-19T11:14:00Z.\n\ntabs ALL → Tickets, Scripts",
    project: "Hub", type: "Audit", priority: "Low", status: "New",
    submitted_by: "Drew", submitted_at: "2026-04-19T11:14:00Z",
    assignee: "", notes: "", resolved_at: "", linked_items: "",
  },
  {
    ticket_id: "TKT-9005", title: "Admin change: alex@eclatech.test — role admin → editor",
    description: "Changed by Drew at 2026-04-12T09:02:00Z.\n\nrole admin → editor",
    project: "Hub", type: "Audit", priority: "Low", status: "New",
    submitted_by: "Drew", submitted_at: "2026-04-12T09:02:00Z",
    assignee: "", notes: "", resolved_at: "", linked_items: "",
  },
]

export const MOCK_TICKET_STATS: TicketStats = {
  "New": 0, "Approved": 0, "In Progress": 1, "In Review": 1, "Closed": 12, "Rejected": 0,
}

export const MOCK_MODELS: Model[] = [
  {
    name: "Sofia Cruz", agency: "Premier Talent", agency_link: "",
    rate: "$1,800/day", rank: "Great", notes: "Available For: FPVR, VRH",
    info: "Age: 24 · Last booked: Apr 2026 · LA-based",
    age: "24", last_booked: "Apr 2026", bookings_count: "14",
    location: "Los Angeles", opportunity_score: 88,
    sheet_data: {},
  },
  {
    name: "Jade Lane", agency: "Spotlight", agency_link: "",
    rate: "$1,500/day", rank: "Great", notes: "Available For: VRH, VRA",
    info: "Age: 22 · Last booked: Apr 2026 · Miami-based",
    age: "22", last_booked: "Apr 2026", bookings_count: "9",
    location: "Miami", opportunity_score: 82,
    sheet_data: {},
  },
  {
    name: "Harper Lane", agency: "Independent", agency_link: "",
    rate: "$900/day", rank: "Good", notes: "Available For: NJOI",
    info: "Age: 26 · Last booked: Mar 2026 · NYC-based",
    age: "26", last_booked: "Mar 2026", bookings_count: "4",
    location: "NYC", opportunity_score: 61,
    sheet_data: {},
  },
]

export const MOCK_CALLSHEET_TABS: string[] = ["April 2026", "May 2026", "June 2026"]

export const MOCK_SHOOT_DATES: ShootDate[] = [
  {
    date_key: "2026-05-03",
    date_display: "Sun, May 3",
    scenes: [
      { date_raw: "2026-05-03", studio: "FuckPassVR", type: "BG",
        female: "Sofia Cruz", male: "Mark Stone",
        agency: "Premier Talent", male_agency: "Rep Co" },
      { date_raw: "2026-05-03", studio: "VRAllure", type: "Solo",
        female: "Maya Knox", male: "",
        agency: "Spotlight", male_agency: "" },
    ],
  },
  {
    date_key: "2026-05-06",
    date_display: "Wed, May 6",
    scenes: [
      { date_raw: "2026-05-06", studio: "VRHush", type: "BG",
        female: "Jade Lane", male: "Daniel Cole",
        agency: "Spotlight", male_agency: "Rep Co" },
    ],
  },
]

export const MOCK_SCRIPT_TABS: string[] = [
  "FPVR - April", "FPVR - May", "VRH - May", "VRA - May", "NJOI - May",
]

export function filterScenes(filters?: {
  studio?: string
  missing_only?: boolean
  search?: string
  page?: number
  limit?: number
}): Scene[] {
  let out = [...MOCK_SCENES]
  if (filters?.studio) out = out.filter(s => s.studio === filters.studio)
  if (filters?.missing_only) {
    out = out.filter(s => !(s.has_description && s.has_videos && s.has_thumbnail && s.has_photos && s.has_storyboard))
  }
  if (filters?.search) {
    const q = filters.search.toLowerCase()
    out = out.filter(s =>
      s.title.toLowerCase().includes(q) ||
      s.performers.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q),
    )
  }
  if (filters?.limit) out = out.slice(0, filters.limit)
  return out
}

// ═══════════════════════════════════════════════════════════════════════
// Shoot Board fixtures — covers yesterday-complete, stuck, upcoming
// ═══════════════════════════════════════════════════════════════════════
import type { Shoot, SceneAssetState, AssetType } from "./api"

const SHOOT_ASSET_TYPES: AssetType[] = [
  "script_done", "call_sheet_sent", "legal_run", "grail_run",
  "bg_edit_uploaded", "solo_uploaded", "title_done",
  "encoded_uploaded", "photoset_uploaded",
  "storyboard_uploaded", "legal_docs_uploaded",
]

function mockAssets(overrides: Partial<Record<AssetType, SceneAssetState["status"]>> = {}): SceneAssetState[] {
  return SHOOT_ASSET_TYPES.map(at => ({
    asset_type: at,
    status: overrides[at] ?? "not_present",
    first_seen_at: overrides[at] && overrides[at] !== "not_present" ? "2026-04-15T03:00:00+00:00" : "",
    validated_at: overrides[at] === "validated" ? "2026-04-15T03:00:00+00:00" : "",
    last_checked_at: "2026-04-17T19:00:00+00:00",
    validity: [],
  }))
}

export const MOCK_SHOOTS: Shoot[] = [
  // 1) Upcoming shoot — pristine, all not_present
  {
    shoot_id: "2026-04-20-sophia-locke",
    shoot_date: "2026-04-20",
    female_talent: "Sophia Locke",
    female_agency: "OC Models",
    female_rate: "$2,400",
    female_payment_name: "Sophia Anne Locklear",
    male_talent: "",
    male_agency: "",
    destination: "",
    location: "",
    home_owner: "David",
    source_tab: "April 2026",
    status: "active",
    aging_hours: 0,
    scenes: [
      {
        scene_id: "",
        studio: "FuckPassVR",
        scene_type: "BGCP",
        grail_tab: "FPVR",
        position: 1,
        title: "",
        performers: "Sophia Locke",
        has_thumbnail: false,
        mega_path: "",
        assets: mockAssets(),
      },
      {
        scene_id: "",
        studio: "NaughtyJOI",
        scene_type: "JOI",
        grail_tab: "NNJOI",
        position: 2,
        title: "",
        performers: "Sophia Locke",
        has_thumbnail: false,
        mega_path: "",
        assets: mockAssets(),
      },
    ],
  },
  // 2) Yesterday — BG validated, Solo still in flight
  {
    shoot_id: "2026-04-16-harley-love",
    shoot_date: "2026-04-16",
    female_talent: "Harley Love",
    female_agency: "Invision Models",
    female_rate: "$1,800",
    female_payment_name: "Harley Morgan Lovell",
    male_talent: "Mike Mancini",
    male_agency: "Independent",
    male_rate: "$900",
    male_payment_name: "Michael A. Mancini",
    destination: "",
    location: "Studio B",
    home_owner: "David",
    source_tab: "April 2026",
    status: "active",
    aging_hours: 26,
    scenes: [
      {
        scene_id: "VRH0764",
        studio: "VRHush",
        scene_type: "BGCP",
        grail_tab: "VRH",
        position: 1,
        title: "Harley Unbound",
        performers: "Harley Love / Mike Mancini",
        has_thumbnail: true,
        mega_path: "/Grail/VRH/VRH0764",
        assets: mockAssets({
          script_done: "validated",
          call_sheet_sent: "validated",
          legal_run: "validated",
          grail_run: "validated",
          bg_edit_uploaded: "validated",
          title_done: "validated",
          encoded_uploaded: "validated",
          photoset_uploaded: "available",
        }),
      },
      {
        scene_id: "VRA0522",
        studio: "VRAllure",
        scene_type: "Solo",
        grail_tab: "VRA",
        position: 2,
        title: "",
        performers: "Harley Love",
        has_thumbnail: true,
        mega_path: "/Grail/VRA/VRA0522",
        assets: mockAssets({
          script_done: "validated",
          grail_run: "validated",
          photoset_uploaded: "validated",
          storyboard_uploaded: "validated",
        }),
      },
    ],
  },
  // 3) Stuck — shoot from 4 days ago, photoset never went up → red
  {
    shoot_id: "2026-04-13-agatha-vega",
    shoot_date: "2026-04-13",
    female_talent: "Agatha Vega",
    female_agency: "The Bakery Talent",
    male_talent: "Mike Mancini",
    male_agency: "Independent",
    destination: "",
    location: "",
    home_owner: "David",
    source_tab: "April 2026",
    status: "active",
    aging_hours: 98,
    scenes: [
      {
        scene_id: "VRH0762",
        studio: "VRHush",
        scene_type: "BG",
        grail_tab: "VRH",
        position: 1,
        title: "Blurred Lines",
        performers: "Agatha Vega / Mike Mancini",
        has_thumbnail: true,
        mega_path: "/Grail/VRH/VRH0762",
        assets: mockAssets({
          script_done: "validated",
          call_sheet_sent: "validated",
          legal_run: "validated",
          grail_run: "validated",
          bg_edit_uploaded: "validated",
          title_done: "validated",
          encoded_uploaded: "validated",
          photoset_uploaded: "stuck",
          storyboard_uploaded: "validated",
        }).map(a =>
          a.asset_type === "photoset_uploaded"
            ? { ...a, validity: [{ check: "count", status: "fail", message: "Expected ≥1 files, found 0" }] }
            : a,
        ),
      },
      {
        scene_id: "",
        studio: "NaughtyJOI",
        scene_type: "JOI",
        grail_tab: "NNJOI",
        position: 2,
        title: "",
        performers: "Agatha Vega",
        has_thumbnail: false,
        mega_path: "",
        assets: mockAssets(),
      },
    ],
  },
  // 4-5) Two extra shoots on the same day as #2 so the calendar cell triggers
  // the "+N more" overflow popover. Without this, dev-mock never exercises it.
  {
    shoot_id: "2026-04-16-jade-lane",
    shoot_date: "2026-04-16",
    female_talent: "Jade Lane",
    female_agency: "Spiegler",
    male_talent: "Daniel Cole",
    male_agency: "Independent",
    destination: "",
    location: "",
    home_owner: "David",
    source_tab: "April 2026",
    status: "active",
    aging_hours: 26,
    scenes: [
      {
        scene_id: "FPVR0211",
        studio: "FuckPassVR",
        scene_type: "BG",
        grail_tab: "FPVR",
        position: 1,
        title: "House Sitter",
        performers: "Jade Lane / Daniel Cole",
        has_thumbnail: true,
        mega_path: "/Grail/FPVR/FPVR0211",
        assets: mockAssets({
          script_done: "validated",
          call_sheet_sent: "validated",
          legal_run: "validated",
        }),
      },
    ],
  },
  {
    shoot_id: "2026-04-16-elena-rivers",
    shoot_date: "2026-04-16",
    female_talent: "Elena Rivers",
    female_agency: "OC Models",
    male_talent: "",
    male_agency: "",
    destination: "",
    location: "",
    home_owner: "David",
    source_tab: "April 2026",
    status: "active",
    aging_hours: 26,
    scenes: [
      {
        scene_id: "",
        studio: "NaughtyJOI",
        scene_type: "JOI",
        grail_tab: "NNJOI",
        position: 1,
        title: "",
        performers: "Elena Rivers",
        has_thumbnail: false,
        mega_path: "",
        assets: mockAssets(),
      },
    ],
  },
]

