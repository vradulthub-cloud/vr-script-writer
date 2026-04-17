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
