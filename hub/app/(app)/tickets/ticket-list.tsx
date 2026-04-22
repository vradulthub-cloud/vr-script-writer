"use client"

import React, { useState, useMemo, useEffect, useRef, useDeferredValue } from "react"
import { X, ChevronRight, ChevronDown, Search } from "lucide-react"
import { ErrorAlert } from "@/components/ui/error-alert"
import { PageHeader } from "@/components/ui/page-header"
import { StudioFilter } from "@/components/ui/studio-filter"
import { api, type Ticket, type TicketCreate, type TicketUpdate, type UserProfile } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { formatApiError } from "@/lib/errors"

const PRIORITY_COLOR: Record<string, string> = {
  Critical: "var(--color-err)",
  High:     "var(--color-njoi)",
  Medium:   "var(--color-warn)",
  Low:      "var(--color-text-muted)",
}

const STATUS_COLOR: Record<string, string> = {
  "New":         "var(--color-text)",
  "Approved":    "var(--color-ok)",
  "In Progress": "var(--color-fpvr)",
  "In Review":   "var(--color-lime)",
  "Closed":      "var(--color-text-faint)",
  "Rejected":    "var(--color-err)",
}

const STAT_CONFIGS = [
  { key: "New",         label: "New",         color: "var(--color-text)" },
  { key: "Approved",    label: "Approved",    color: "var(--color-ok)" },
  { key: "In Progress", label: "In Progress", color: "var(--color-fpvr)" },
  { key: "In Review",   label: "In Review",   color: "var(--color-lime)" },
  { key: "Closed",      label: "Closed",      color: "var(--color-text-faint)" },
  { key: "Rejected",    label: "Rejected",    color: "var(--color-err)" },
] as const

const TICKET_STATUSES = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
// Projects whose tickets are mostly AI-talking-about-AI work (engineering
// on the hub itself, user permission audits). Hidden when Content Only is on.
const ENGINEERING_PROJECTS = new Set(["Hub", "Eclatech Hub", "Script Writer"])
const ADMIN_ONLY_STATUSES = new Set(["Closed", "Rejected"])
const DESCRIPTION_MAX = 4000
const LINKED_ITEMS_MAX = 500
const NOTE_MAX = 2000
const PRIORITIES = ["Low", "Medium", "High", "Critical"]
const PRIORITY_ORDER = ["Critical", "High", "Medium", "Low"]
const STATUS_ORDER = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
const PROJECTS = ["", "Hub", "Content", "Infrastructure", "Scripts", "Descriptions", "MEGA", "Other"]
const TYPES = ["", "Bug", "Feature", "Task", "Question", "Improvement"]

type SortKey = "date" | "priority" | "status"

const COLUMNS: { key: string; label: string; sort?: SortKey }[] = [
  { key: "id", label: "ID" },
  { key: "title", label: "Title" },
  { key: "studio", label: "Studio" },
  { key: "priority", label: "Priority", sort: "priority" },
  { key: "status", label: "Status", sort: "status" },
  { key: "date", label: "Created", sort: "date" },
]

const DATE_FMT = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" })

// Map scene ID prefixes (the leading letters before the 4-digit number) to
// the canonical studio key used everywhere else in the app. Scene IDs look
// like "FPVR1284" / "VRH0987" / "VRA0419" / "NJOI0042"; the prefix is the
// only reliable studio anchor we get on tickets, since the `project` field
// is freeform ("Hub", "Content", "Other"...) and rarely names a studio.
const SCENE_PREFIX_TO_STUDIO: Record<string, string> = {
  FPVR: "FuckPassVR",
  VRH:  "VRHush",
  VRA:  "VRAllure",
  NJOI: "NaughtyJOI",
  NNJOI: "NaughtyJOI",  // Grail-tab variant — see CLAUDE.md studio mapping table.
}
const SCENE_ID_RE = /\b(NNJOI|NJOI|FPVR|VRH|VRA)[-_]?\d{2,5}\b/gi

/**
 * Extract every studio referenced by a ticket via its linked_items field.
 * Returns the set of full studio keys ("FuckPassVR", "VRHush", ...).
 * Empty set when no scene IDs are linked — those tickets pass any studio
 * filter only when "All" is selected.
 */
function studiosFromTicket(t: Ticket): Set<string> {
  const out = new Set<string>()
  const haystack = `${t.linked_items ?? ""} ${t.title ?? ""}`
  let m: RegExpExecArray | null
  SCENE_ID_RE.lastIndex = 0
  while ((m = SCENE_ID_RE.exec(haystack)) !== null) {
    const prefix = m[1].toUpperCase()
    const studio = SCENE_PREFIX_TO_STUDIO[prefix]
    if (studio) out.add(studio)
  }
  return out
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return DATE_FMT.format(d)
}

interface Props {
  tickets: Ticket[]
  users: UserProfile[]
  error: string | null
  idToken: string | undefined
  userRole: string
  /** Pre-select a status filter on mount. "open" maps to the "Active" preset. */
  defaultStatusFilter?: string
}

export function TicketList({ tickets: initialTickets, users, error, idToken: serverIdToken, userRole, defaultStatusFilter }: Props) {
  const isAdmin = userRole.toLowerCase() === "admin"
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [tickets, setTickets] = useState<Ticket[]>(initialTickets)
  const [statusFilter, setStatusFilter] = useState(() => {
    if (!defaultStatusFilter) return "Active"
    if (defaultStatusFilter === "open") return "Active"
    return defaultStatusFilter
  })
  // Studio filter — null means "All studios". Persisted across page reloads
  // so a user working primarily in one studio doesn't have to re-select it.
  const [studioFilter, setStudioFilter] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    const raw = window.localStorage.getItem("hub:tickets:studio")
    return raw && raw !== "null" ? raw : null
  })
  useEffect(() => {
    if (typeof window === "undefined") return
    window.localStorage.setItem("hub:tickets:studio", studioFilter ?? "null")
  }, [studioFilter])
  const [searchQuery, setSearchQuery] = useState("")
  const [sortKey, setSortKey] = useState<SortKey>("date")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")
  const [expanded, setExpanded] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  // Editing state
  const [editStatus, setEditStatus] = useState("")
  const [editAssignee, setEditAssignee] = useState("")
  const [editNote, setEditNote] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [flashId, setFlashId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkStatus, setBulkStatus] = useState<string>("")
  const [bulkAssignee, setBulkAssignee] = useState<string>("")
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkMsg, setBulkMsg] = useState<string | null>(null)

  // "Content only" filter — hides engineering/audit tickets that are
  // mostly AI chatter about the hub itself. Default on. Persisted so a
  // user's choice survives refresh.
  const [contentOnly, setContentOnly] = useState<boolean>(() => {
    if (typeof window === "undefined") return true
    const raw = window.localStorage.getItem("hub:tickets:contentOnly")
    return raw === null ? true : raw === "1"
  })
  useEffect(() => {
    if (typeof window === "undefined") return
    window.localStorage.setItem("hub:tickets:contentOnly", contentOnly ? "1" : "0")
  }, [contentOnly])

  // Create form state
  const [createForm, setCreateForm] = useState<TicketCreate>({
    title: "",
    description: "",
    project: "",
    type: "",
    priority: "Medium",
    linked_items: "",
    status: "New",
    assignee: "",
    notify: [],
  })
  const [creating, setCreating] = useState(false)
  const [createErr, setCreateErr] = useState<string | null>(null)
  const [newTicketId, setNewTicketId] = useState<string | null>(null)

  const modalRef = useRef<HTMLDivElement>(null)
  const createFormRef = useRef(createForm)
  useEffect(() => { createFormRef.current = createForm }, [createForm])

  // ── Derived state ────────────────────────────────────────────────

  const counts = useMemo(() => {
    const result: Record<string, number> = {}
    for (const t of tickets) {
      result[t.status] = (result[t.status] ?? 0) + 1
    }
    return result
  }, [tickets])

  const activeCount = useMemo(() => tickets.filter(t => t.status !== "Closed" && t.status !== "Rejected").length, [tickets])

  // Defer heavy filter work behind the input — keeps typing snappy
  const deferredSearch = useDeferredValue(searchQuery)

  // Per-studio counts on the chip filter. Computed against the current
  // status/content scope so the badge reflects "FPVR open tickets", not
  // "FPVR tickets ever". Otherwise the badges look misleading after the
  // user narrows the view.
  const studioCounts = useMemo(() => {
    const scope = statusFilter === "All"
      ? tickets
      : statusFilter === "Active"
        ? tickets.filter(t => t.status !== "Closed" && t.status !== "Rejected")
        : tickets.filter(t => t.status === statusFilter)
    const filtered = contentOnly
      ? scope.filter(t => !ENGINEERING_PROJECTS.has(t.project) && t.type !== "Audit")
      : scope
    const out: Record<string, number> = { FuckPassVR: 0, VRHush: 0, VRAllure: 0, NaughtyJOI: 0 }
    for (const t of filtered) {
      for (const s of studiosFromTicket(t)) {
        if (out[s] !== undefined) out[s] += 1
      }
    }
    return out
  }, [tickets, statusFilter, contentOnly])

  const displayTickets = useMemo(() => {
    let result = statusFilter === "All"
      ? tickets
      : statusFilter === "Active"
        ? tickets.filter(t => t.status !== "Closed" && t.status !== "Rejected")
        : tickets.filter(t => t.status === statusFilter)
    if (contentOnly) {
      // "Content only" hides engineering/audit tickets so the list isn't
      // dominated by AI-generated work about the hub's own code.
      result = result.filter(t => !ENGINEERING_PROJECTS.has(t.project) && t.type !== "Audit")
    }
    if (studioFilter) {
      // Tickets without any linked scene IDs drop out when a studio is
      // selected — that's the right behavior, since the user explicitly
      // narrowed scope to one studio's work.
      result = result.filter(t => studiosFromTicket(t).has(studioFilter))
    }
    if (deferredSearch.trim()) {
      const q = deferredSearch.toLowerCase()
      result = result.filter(t =>
        t.title.toLowerCase().includes(q) ||
        t.ticket_id.toLowerCase().includes(q) ||
        (t.description && t.description.toLowerCase().includes(q))
      )
    }
    return [...result].sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case "date":
          cmp = (a.submitted_at || "").localeCompare(b.submitted_at || "")
          break
        case "priority":
          cmp = PRIORITY_ORDER.indexOf(a.priority) - PRIORITY_ORDER.indexOf(b.priority)
          break
        case "status":
          cmp = STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)
          break
      }
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [tickets, statusFilter, contentOnly, studioFilter, deferredSearch, sortKey, sortDir])

  // ── Keyboard: Escape ─────────────────────────────────────────────

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      if (showCreate) {
        e.preventDefault()
        const f = createFormRef.current
        const hasContent = f.title.trim() || (f.description ?? "").trim() || f.project || f.type || (f.linked_items ?? "").trim()
        if (hasContent && !window.confirm("Discard unsaved changes?")) return
        setShowCreate(false)
        setCreateForm({ title: "", description: "", project: "", type: "", priority: "Medium", linked_items: "" })
        setCreateErr(null)
      } else if (expanded) {
        setExpanded(null)
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [showCreate, expanded])

  // ── Focus trap in modal ──────────────────────────────────────────

  useEffect(() => {
    if (!showCreate) return
    const modal = modalRef.current
    if (!modal) return
    const focusable = modal.querySelectorAll<HTMLElement>(
      "input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])"
    )
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    function trapTab(e: KeyboardEvent) {
      if (e.key !== "Tab") return
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    modal.addEventListener("keydown", trapTab)
    return () => modal.removeEventListener("keydown", trapTab)
  }, [showCreate])

  // ── Timer cleanup (prevent setState-on-unmount leaks) ────────────

  useEffect(() => {
    if (!flashId) return
    const t = setTimeout(() => setFlashId(null), 1200)
    return () => clearTimeout(t)
  }, [flashId])

  useEffect(() => {
    if (!newTicketId) return
    const t = setTimeout(() => setNewTicketId(null), 600)
    return () => clearTimeout(t)
  }, [newTicketId])

  // ── Handlers ─────────────────────────────────────────────────────

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir(key === "date" ? "desc" : "asc")
    }
  }

  function openTicket(ticket: Ticket) {
    if (expanded === ticket.ticket_id) {
      setExpanded(null)
      return
    }
    setExpanded(ticket.ticket_id)
    setEditStatus(ticket.status)
    setEditAssignee(ticket.assignee || "")
    setEditNote("")
    setSaveMsg(null)
  }

  function closeCreateModal() {
    const f = createFormRef.current
    const hasContent = f.title.trim() || (f.description ?? "").trim() || f.project || f.type || (f.linked_items ?? "").trim()
    if (hasContent && !window.confirm("Discard unsaved changes?")) return
    setShowCreate(false)
    setCreateForm({ title: "", description: "", project: "", type: "", priority: "Medium", linked_items: "" })
    setCreateErr(null)
  }

  /**
   * Apply a one-click quick action (QC Fixed, Verify, Approve, etc.)
   * without going through the full edit form. Writes a descriptive
   * timestamped note automatically so the timeline still reflects who
   * did what.
   */
  async function applyQuickAction(ticketId: string, body: TicketUpdate): Promise<void> {
    setSaving(true)
    setSaveMsg(null)
    try {
      const updated = await client.tickets.update(ticketId, body)
      setTickets(prev => prev.map(t => t.ticket_id === ticketId ? updated : t))
      setEditStatus(updated.status)
      setEditAssignee(updated.assignee || "")
      setFlashId(ticketId)
      setSaveMsg("Saved.")
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save"))
    } finally {
      setSaving(false)
    }
  }

  async function saveUpdate(ticketId: string) {
    setSaving(true)
    setSaveMsg(null)
    const body: TicketUpdate = {}
    const ticket = tickets.find(t => t.ticket_id === ticketId)
    if (!ticket) { setSaving(false); return }
    if (editStatus !== ticket.status) {
      if (!isAdmin && ADMIN_ONLY_STATUSES.has(editStatus)) {
        setSaving(false)
        setSaveMsg(`Only admins can set status to ${editStatus}.`)
        return
      }
      body.status = editStatus
    }
    if (editAssignee !== (ticket.assignee ?? "")) body.assignee = editAssignee
    if (editNote.trim()) body.note = editNote.trim()
    if (Object.keys(body).length === 0) { setSaving(false); setSaveMsg("No changes."); return }
    try {
      const updated = await client.tickets.update(ticketId, body)
      setTickets(prev => prev.map(t => t.ticket_id === ticketId ? updated : t))
      setSaveMsg("Saved.")
      setEditNote("")
      setFlashId(ticketId)
    } catch (e) {
      setSaveMsg(formatApiError(e, "Save"))
    } finally {
      setSaving(false)
    }
  }

  async function createTicket() {
    if (!createForm.title.trim()) return
    setCreating(true)
    setCreateErr(null)
    try {
      const created = await client.tickets.create({
        ...createForm,
        title: createForm.title.trim(),
      })
      setTickets(prev => [created, ...prev])
      setShowCreate(false)
      setCreateForm({ title: "", description: "", project: "", type: "", priority: "Medium", linked_items: "", status: "New", assignee: "", notify: [] })
      setNewTicketId(created.ticket_id)
    } catch (e) {
      setCreateErr(formatApiError(e, "Create ticket"))
    } finally {
      setCreating(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div>
      {!error && (
        <PageHeader
          title="Tickets"
          eyebrow={`${activeCount} active · ${tickets.length} total`}
          actions={
            <>
              <div className="flex items-center gap-1 rounded-md" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", padding: "3px" }}>
                {([
                  { key: "Active", label: "Active", count: activeCount, color: undefined as string | undefined },
                  { key: "All",    label: "All",    count: tickets.length, color: undefined as string | undefined },
                  ...STAT_CONFIGS.filter(({ key }) => (counts[key] ?? 0) > 0).map(({ key, label, color }) => ({
                    key, label, count: counts[key] ?? 0, color: color as string | undefined,
                  })),
                ]).map(({ key, label, count, color }) => {
                  const isActive = statusFilter === key
                  const chipColor = color ?? (key === "Active" ? "var(--color-lime)" : "var(--color-text-muted)")
                  return (
                    <button
                      key={key}
                      onClick={() => setStatusFilter(key)}
                      aria-pressed={isActive}
                      className="rounded px-2 py-1 transition-colors"
                      style={{
                        fontSize: 11,
                        fontWeight: isActive ? 600 : 400,
                        background: isActive ? "var(--color-elevated)" : "transparent",
                        color: isActive ? chipColor : "var(--color-text-muted)",
                        border: "none",
                      }}
                    >
                      {label} <span className="tabular-nums" style={{ opacity: 0.7 }}>{count}</span>
                    </button>
                  )
                })}
              </div>
              <button
                onClick={() => setContentOnly(v => !v)}
                role="switch"
                aria-checked={contentOnly}
                title={contentOnly
                  ? "Hiding Hub/engineering + audit tickets — click to show everything"
                  : "Showing all tickets — click to hide Hub/engineering + audit"}
                className="rounded transition-colors"
                style={{
                  padding: "4px 10px",
                  fontSize: 11,
                  cursor: "pointer",
                  background: contentOnly ? "color-mix(in srgb, var(--color-lime) 12%, transparent)" : "transparent",
                  color: contentOnly ? "var(--color-lime)" : "var(--color-text-muted)",
                  border: `1px solid ${contentOnly ? "color-mix(in srgb, var(--color-lime) 30%, transparent)" : "var(--color-border)"}`,
                }}
              >
                Content only
              </button>
              <button
                onClick={() => setShowCreate(true)}
                className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                style={{ background: "var(--color-lime)", color: "var(--color-base)" }}
              >
                + New Ticket
              </button>
            </>
          }
        />
      )}

      {/* Filter row — search left, studio chips right. Single line so the
          table starts higher; wraps gracefully on narrow viewports. */}
      {!error && tickets.length > 0 && (
        <div
          className="mb-3"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            justifyContent: "space-between",
          }}
        >
          <div className="relative" style={{ flex: "1 1 280px", maxWidth: 360 }}>
            <Search
              size={12}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: "var(--color-text-faint)" }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search by title, ID, or description…"
              className="w-full pl-7 pr-3 py-1.5 rounded text-xs"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>
          <StudioFilter
            value={studioFilter}
            onChange={setStudioFilter}
            counts={studioCounts}
          />
        </div>
      )}

      {/* Error state */}
      {error && (
        <ErrorAlert className="p-4 text-sm mb-4">
          {error}
          <p className="mt-1 text-xs opacity-70">
            Could not reach the API. Check that the backend service is running.
          </p>
        </ErrorAlert>
      )}

      {/* Empty state */}
      {!error && displayTickets.length === 0 && (
        <div style={{ padding: "32px 0", textAlign: "center" }}>
          <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 8 }}>
            {searchQuery.trim()
              ? `No tickets matching "${searchQuery.trim()}"`
              : statusFilter === "Active"
                ? "No active tickets"
                : statusFilter !== "All"
                  ? `No tickets with status "${statusFilter}"`
                  : "No tickets yet"}
          </p>
          {(statusFilter === "All" || statusFilter === "Active") && !searchQuery.trim() && (
            <button
              onClick={() => setShowCreate(true)}
              className="text-xs font-medium transition-colors"
              style={{ color: "var(--color-lime)" }}
            >
              Create your first ticket
            </button>
          )}
        </div>
      )}

      {/* Bulk action bar — visible when any ticket row is checked */}
      {selected.size > 0 && (
        <div
          className="mb-2 rounded flex items-center gap-2 flex-wrap"
          style={{
            padding: "6px 10px",
            background: "color-mix(in srgb, var(--color-lime) 7%, var(--color-surface))",
            border: "1px solid color-mix(in srgb, var(--color-lime) 25%, var(--color-border))",
            fontSize: 11,
          }}
        >
          <span style={{ color: "var(--color-text)", fontWeight: 500 }}>
            {selected.size} selected
          </span>
          <select
            value={bulkStatus}
            onChange={e => setBulkStatus(e.target.value)}
            disabled={bulkBusy}
            aria-label="Bulk status"
            style={{
              fontSize: 11, padding: "3px 6px", borderRadius: 4,
              background: "var(--color-base)", color: "var(--color-text)",
              border: "1px solid var(--color-border)",
            }}
          >
            <option value="">Set status…</option>
            {TICKET_STATUSES.filter(s => isAdmin || !ADMIN_ONLY_STATUSES.has(s)).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            value={bulkAssignee}
            onChange={e => setBulkAssignee(e.target.value)}
            disabled={bulkBusy}
            aria-label="Bulk assignee"
            style={{
              fontSize: 11, padding: "3px 6px", borderRadius: 4,
              background: "var(--color-base)", color: "var(--color-text)",
              border: "1px solid var(--color-border)",
            }}
          >
            <option value="">Set assignee…</option>
            <option value="__clear__">(Unassign)</option>
            {users.map(u => <option key={u.email} value={u.name}>{u.name}</option>)}
          </select>
          <button
            disabled={bulkBusy || (!bulkStatus && !bulkAssignee)}
            onClick={async () => {
              if (!bulkStatus && !bulkAssignee) return
              setBulkBusy(true); setBulkMsg(null)
              try {
                const res = await client.tickets.bulkUpdate({
                  ticket_ids: [...selected],
                  status: bulkStatus || undefined,
                  assignee: bulkAssignee === "__clear__" ? "" : (bulkAssignee || undefined),
                })
                // Optimistically apply updates locally so the UI reflects it
                setTickets(prev => prev.map(t => {
                  if (!res.updated.includes(t.ticket_id)) return t
                  return {
                    ...t,
                    ...(bulkStatus ? { status: bulkStatus } : {}),
                    ...(bulkAssignee ? { assignee: bulkAssignee === "__clear__" ? "" : bulkAssignee } : {}),
                  }
                }))
                setSelected(new Set())
                setBulkStatus(""); setBulkAssignee("")
                const parts = [`${res.updated.length} updated`]
                if (res.skipped.length) parts.push(`${res.skipped.length} skipped`)
                setBulkMsg(parts.join(" · "))
              } catch (e) {
                setBulkMsg(formatApiError(e, "Bulk update"))
              } finally {
                setBulkBusy(false)
              }
            }}
            className="px-2.5 py-1 rounded transition-colors"
            style={{
              fontSize: 11, fontWeight: 600,
              background: "var(--color-lime)",
              color: "var(--color-base)",
              border: "none",
              cursor: bulkBusy ? "wait" : (!bulkStatus && !bulkAssignee ? "not-allowed" : "pointer"),
              opacity: (bulkBusy || (!bulkStatus && !bulkAssignee)) ? 0.5 : 1,
            }}
          >
            {bulkBusy ? "Applying…" : "Apply"}
          </button>
          <button
            onClick={() => { setSelected(new Set()); setBulkStatus(""); setBulkAssignee(""); setBulkMsg(null) }}
            style={{
              fontSize: 11, padding: "3px 8px", borderRadius: 4,
              background: "transparent", color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
            }}
          >
            Clear
          </button>
          {bulkMsg && (
            <span style={{ color: bulkMsg.includes("updated") ? "var(--color-ok)" : "var(--color-err)", marginLeft: "auto" }}>
              {bulkMsg}
            </span>
          )}
        </div>
      )}

      {/* Table */}
      {!error && displayTickets.length > 0 && (
        <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                <th
                  scope="col"
                  className="px-3 py-2"
                  style={{ width: 32, fontSize: 11, color: "var(--color-text-muted)" }}
                  onClick={e => e.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    aria-label="Select all visible"
                    checked={displayTickets.length > 0 && displayTickets.every(t => selected.has(t.ticket_id))}
                    ref={el => {
                      if (!el) return
                      const some = displayTickets.some(t => selected.has(t.ticket_id))
                      const all  = displayTickets.every(t => selected.has(t.ticket_id))
                      el.indeterminate = some && !all
                    }}
                    onChange={e => {
                      const next = new Set(selected)
                      if (e.target.checked) {
                        for (const t of displayTickets) next.add(t.ticket_id)
                      } else {
                        for (const t of displayTickets) next.delete(t.ticket_id)
                      }
                      setSelected(next)
                    }}
                  />
                </th>
                {COLUMNS.map(col => (
                  <th
                    key={col.key}
                    scope="col"
                    className={`text-left px-3 py-2 font-medium${col.sort ? " cursor-pointer select-none" : ""}`}
                    style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                    onClick={col.sort ? () => toggleSort(col.sort!) : undefined}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {col.sort && sortKey === col.sort && (
                        <span style={{ fontSize: 8 }}>{sortDir === "asc" ? "↑" : "↓"}</span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayTickets.map((ticket, i) => {
                const isExpanded = expanded === ticket.ticket_id
                const isLast = i === displayTickets.length - 1
                const isNew = newTicketId === ticket.ticket_id
                return (
                  <React.Fragment key={ticket.ticket_id}>
                    <tr
                      className={`transition-colors cursor-pointer${isExpanded ? "" : " hover:bg-[--color-elevated]"}`}
                      onClick={() => openTicket(ticket)}
                      aria-expanded={isExpanded}
                      style={{
                        borderBottom: !isExpanded && !isLast ? "1px solid var(--color-border-subtle)" : undefined,
                        background: isExpanded ? "var(--color-surface)" : undefined,
                        animation: isNew ? "fadeIn 350ms var(--ease-out-expo) both" : undefined,
                      }}
                    >
                      <td
                        className="px-3 py-2.5"
                        style={{ width: 32 }}
                        onClick={e => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          aria-label={`Select ${ticket.ticket_id}`}
                          checked={selected.has(ticket.ticket_id)}
                          onChange={e => {
                            const next = new Set(selected)
                            if (e.target.checked) next.add(ticket.ticket_id)
                            else next.delete(ticket.ticket_id)
                            setSelected(next)
                          }}
                        />
                      </td>
                      <td className="px-3 py-2.5" style={{ whiteSpace: "nowrap" }}>
                        <span className="flex items-center gap-1.5">
                          <span style={{ color: "var(--color-text-faint)", flexShrink: 0, display: "flex", alignItems: "center" }}>
                            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                          </span>
                          <span className="font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                            {ticket.ticket_id}
                          </span>
                        </span>
                      </td>
                      <td className="px-3 py-2.5" style={{ fontSize: 12 }}>
                        <span className="line-clamp-1">{ticket.title}</span>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <StudioCellChips ticket={ticket} />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <Badge label={ticket.priority} color={PRIORITY_COLOR[ticket.priority] ?? "var(--color-text-muted)"} />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <Badge label={ticket.status} color={STATUS_COLOR[ticket.status] ?? "var(--color-text-muted)"} />
                      </td>
                      <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                        <time dateTime={ticket.submitted_at || undefined}>{formatDate(ticket.submitted_at)}</time>
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr
                        data-saved={flashId === ticket.ticket_id ? true : undefined}
                        style={{ borderBottom: !isLast ? "1px solid var(--color-border-subtle)" : undefined }}
                      >
                        <td colSpan={7} className="px-3 pb-4 pt-2" style={{ background: "var(--color-surface)" }}>
                          <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
                            {/* Left: description + meta */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                              {ticket.description && (
                                <p style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.6, marginBottom: 8 }}>
                                  {ticket.description}
                                </p>
                              )}
                              <div className="flex flex-wrap gap-x-4 gap-y-1">
                                {ticket.project && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Project: <span style={{ color: "var(--color-text)" }}>{ticket.project}</span>
                                  </span>
                                )}
                                {ticket.type && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Type: <span style={{ color: "var(--color-text)" }}>{ticket.type}</span>
                                  </span>
                                )}
                                {ticket.submitted_by && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Reporter: <span style={{ color: "var(--color-text)" }}>{ticket.submitted_by}</span>
                                  </span>
                                )}
                                {ticket.assignee && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Assignee: <span style={{ color: "var(--color-text)" }}>{ticket.assignee}</span>
                                  </span>
                                )}
                                {ticket.linked_items && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Linked: <span style={{ color: "var(--color-text)" }}>{ticket.linked_items}</span>
                                  </span>
                                )}
                                {ticket.resolved_at && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Resolved: <span style={{ color: "var(--color-text)" }}><time dateTime={ticket.resolved_at}>{formatDate(ticket.resolved_at)}</time></span>
                                  </span>
                                )}
                              </div>
                              {ticket.notes && (
                                <div style={{ marginTop: 8 }}>
                                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontWeight: 500, letterSpacing: "0.04em", textTransform: "uppercase" }}>Notes</span>
                                  <NotesTimeline raw={ticket.notes} />
                                </div>
                              )}

                              {/* Quick-action bar — status-aware shortcuts
                                  mirroring the Streamlit QC / Verify / Approve flows */}
                              <TicketQuickActions
                                ticket={ticket}
                                isAdmin={isAdmin}
                                busy={saving}
                                onAction={(update) => applyQuickAction(ticket.ticket_id, update)}
                              />
                            </div>

                            {/* Right: edit panel */}
                            <div style={{ width: "min(260px, 100%)", flexShrink: 1 }}>
                              <div className="flex flex-col gap-2">
                                <div>
                                  <label htmlFor={`edit-status-${ticket.ticket_id}`} style={{ fontSize: 10, color: "var(--color-text-faint)", display: "block", marginBottom: 3 }}>STATUS</label>
                                  <select
                                    id={`edit-status-${ticket.ticket_id}`}
                                    value={editStatus}
                                    onChange={e => setEditStatus(e.target.value)}
                                    className="w-full px-2 py-1.5 rounded text-xs"
                                    style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", color: STATUS_COLOR[editStatus] ?? "var(--color-text)" }}
                                  >
                                    {TICKET_STATUSES.map(s => {
                                      // Keep the current status selectable even for non-admins so they see
                                      // the true state of the ticket; only block *transitioning into* admin-only states.
                                      const isLocked = !isAdmin && ADMIN_ONLY_STATUSES.has(s) && s !== ticket.status
                                      return <option key={s} value={s} disabled={isLocked}>{s}{isLocked ? " — admin only" : ""}</option>
                                    })}
                                  </select>
                                </div>
                                <div>
                                  <label htmlFor={`edit-assignee-${ticket.ticket_id}`} style={{ fontSize: 10, color: "var(--color-text-faint)", display: "block", marginBottom: 3 }}>ASSIGNEE</label>
                                  {users.length > 0 ? (
                                    <select
                                      id={`edit-assignee-${ticket.ticket_id}`}
                                      value={editAssignee}
                                      onChange={e => setEditAssignee(e.target.value)}
                                      className="w-full px-2 py-1.5 rounded text-xs"
                                      style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", color: editAssignee ? "var(--color-text)" : "var(--color-text-muted)" }}
                                    >
                                      <option value="">Unassigned</option>
                                      {users.map(u => <option key={u.email} value={u.name}>{u.name}</option>)}
                                    </select>
                                  ) : (
                                    <input
                                      id={`edit-assignee-${ticket.ticket_id}`}
                                      type="text"
                                      value={editAssignee}
                                      onChange={e => setEditAssignee(e.target.value)}
                                      placeholder="Name or email"
                                      className="w-full px-2 py-1.5 rounded text-xs"
                                      style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                                    />
                                  )}
                                </div>
                                <div>
                                  <label htmlFor={`edit-note-${ticket.ticket_id}`} style={{ fontSize: 10, color: "var(--color-text-faint)", display: "block", marginBottom: 3 }}>ADD NOTE</label>
                                  <textarea
                                    id={`edit-note-${ticket.ticket_id}`}
                                    value={editNote}
                                    onChange={e => setEditNote(e.target.value)}
                                    rows={2}
                                    maxLength={NOTE_MAX}
                                    placeholder="Optional update note…"
                                    className="w-full px-2 py-1.5 rounded text-xs resize-none"
                                    style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                                  />
                                </div>
                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={(e) => { e.stopPropagation(); saveUpdate(ticket.ticket_id) }}
                                    disabled={saving}
                                    className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                                    style={{ background: "var(--color-lime)", color: "var(--color-base)", opacity: saving ? 0.5 : 1 }}
                                  >
                                    {saving ? "Saving…" : "Save Changes"}
                                  </button>
                                  {saveMsg && (
                                    <span role="status" aria-live="polite" style={{ fontSize: 11, color: saveMsg === "Saved." ? "var(--color-ok)" : saveMsg === "No changes." ? "var(--color-text-muted)" : "var(--color-err)" }}>
                                      {saveMsg}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create ticket modal */}
      {showCreate && (
        <div
          className="fixed inset-0 flex items-center justify-center"
          style={{ background: "oklch(0% 0 0 / 60%)", zIndex: 50 }}
          onClick={e => { if (e.target === e.currentTarget) closeCreateModal() }}
        >
          <div
            ref={modalRef}
            className="rounded-lg"
            style={{ background: "var(--color-base)", border: "1px solid var(--color-border)", width: 480, maxWidth: "calc(100vw - 32px)", padding: "20px 24px" }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>New Ticket</h2>
              <button onClick={closeCreateModal} aria-label="Close" className="transition-colors hover:opacity-70" style={{ color: "var(--color-text-muted)", display: "flex", alignItems: "center" }}>
                <X size={14} />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <div>
                <label htmlFor="create-title" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Title *</label>
                <input id="create-title" type="text" value={createForm.title} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} placeholder="Short summary of the issue or request" autoFocus maxLength={200} className="w-full px-2.5 py-1.5 rounded text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
              </div>
              <div>
                <label htmlFor="create-description" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Description</label>
                <textarea id="create-description" value={createForm.description} onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))} rows={3} maxLength={DESCRIPTION_MAX} placeholder="Steps to reproduce, expected behavior, context…" className="w-full px-2.5 py-1.5 rounded text-xs resize-none" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
              </div>
              <div className="flex gap-3">
                <div style={{ flex: 1 }}>
                  <label htmlFor="create-project" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Project</label>
                  <select id="create-project" value={createForm.project} onChange={e => setCreateForm(f => ({ ...f, project: e.target.value }))} className="w-full px-2.5 py-1.5 rounded text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: createForm.project ? "var(--color-text)" : "var(--color-text-muted)" }}>
                    {PROJECTS.map(p => <option key={p} value={p}>{p || "— Select —"}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label htmlFor="create-type" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Type</label>
                  <select id="create-type" value={createForm.type} onChange={e => setCreateForm(f => ({ ...f, type: e.target.value }))} className="w-full px-2.5 py-1.5 rounded text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: createForm.type ? "var(--color-text)" : "var(--color-text-muted)" }}>
                    {TYPES.map(t => <option key={t} value={t}>{t || "— Select —"}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label htmlFor="create-priority" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Priority</label>
                  <select id="create-priority" value={createForm.priority} onChange={e => setCreateForm(f => ({ ...f, priority: e.target.value }))} className="w-full px-2.5 py-1.5 rounded text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: PRIORITY_COLOR[createForm.priority ?? "Medium"] ?? "var(--color-text)" }}>
                    {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex gap-3">
                <div style={{ flex: 1 }}>
                  <label htmlFor="create-status" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Status</label>
                  <select
                    id="create-status"
                    value={createForm.status ?? "New"}
                    onChange={e => setCreateForm(f => ({ ...f, status: e.target.value }))}
                    className="w-full px-2.5 py-1.5 rounded text-xs"
                    style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                  >
                    {TICKET_STATUSES.filter(s => isAdmin || !ADMIN_ONLY_STATUSES.has(s)).map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 2 }}>
                  <label htmlFor="create-assignee" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Assignee</label>
                  <select
                    id="create-assignee"
                    value={createForm.assignee ?? ""}
                    onChange={e => setCreateForm(f => ({ ...f, assignee: e.target.value }))}
                    className="w-full px-2.5 py-1.5 rounded text-xs"
                    style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: createForm.assignee ? "var(--color-text)" : "var(--color-text-muted)" }}
                  >
                    <option value="">Unassigned</option>
                    {users.map(u => (
                      <option key={u.email} value={u.name}>{u.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="create-linked" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Linked items <span style={{ color: "var(--color-text-faint)" }}>(scene IDs, ticket IDs)</span></label>
                <input id="create-linked" type="text" value={createForm.linked_items} onChange={e => setCreateForm(f => ({ ...f, linked_items: e.target.value }))} maxLength={LINKED_ITEMS_MAX} placeholder="e.g. TKT-0012, SC-1234" className="w-full px-2.5 py-1.5 rounded text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
              </div>
              <div>
                <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>
                  Notify <span style={{ color: "var(--color-text-faint)" }}>(pings these people, in addition to admins)</span>
                </label>
                <div
                  className="rounded"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", padding: "6px 8px", maxHeight: 110, overflowY: "auto" }}
                >
                  {users.length === 0 ? (
                    <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>No teammates available.</span>
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "4px 12px" }}>
                      {users.map(u => {
                        const checked = (createForm.notify ?? []).includes(u.name)
                        return (
                          <label key={u.email} style={{ fontSize: 11, color: "var(--color-text)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={e => setCreateForm(f => {
                                const next = new Set(f.notify ?? [])
                                if (e.target.checked) next.add(u.name)
                                else next.delete(u.name)
                                return { ...f, notify: Array.from(next) }
                              })}
                            />
                            <span>{u.name}</span>
                          </label>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {createErr && <ErrorAlert className="mt-3 text-xs">{createErr}</ErrorAlert>}

            <div className="flex justify-end gap-2 mt-4">
              <button onClick={closeCreateModal} className="px-3 py-1.5 rounded text-xs transition-colors" style={{ background: "transparent", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}>
                Cancel
              </button>
              <button onClick={createTicket} disabled={creating || !createForm.title.trim()} className="px-3 py-1.5 rounded text-xs font-semibold transition-colors" style={{ background: "var(--color-lime)", color: "var(--color-base)", opacity: (creating || !createForm.title.trim()) ? 0.5 : 1, cursor: (creating || !createForm.title.trim()) ? "not-allowed" : "pointer" }}>
                {creating ? "Creating…" : "Create Ticket"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Per-row studio chips. Reuses studiosFromTicket so the column always
 * agrees with the studio filter — there's never a row visible under
 * "VRH" that doesn't show a VRH chip here. Renders nothing for tickets
 * with no scene linkage so the column doesn't get noisy.
 */
function StudioCellChips({ ticket }: { ticket: Ticket }) {
  const studios = studiosFromTicket(ticket)
  if (studios.size === 0) {
    return <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>—</span>
  }
  return (
    <span style={{ display: "inline-flex", gap: 4 }}>
      {[...studios].map(s => (
        <Badge
          key={s}
          label={(s === "FuckPassVR" && "FPVR") || (s === "VRHush" && "VRH") || (s === "VRAllure" && "VRA") || (s === "NaughtyJOI" && "NJOI") || s}
          color={
            s === "FuckPassVR" ? "var(--color-fpvr)"
            : s === "VRHush"   ? "var(--color-vrh)"
            : s === "VRAllure" ? "var(--color-vra)"
            : s === "NaughtyJOI" ? "var(--color-njoi)"
            : "var(--color-text-muted)"
          }
        />
      ))}
    </span>
  )
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-sm"
      style={{ fontSize: 10, fontWeight: 500, letterSpacing: "0.02em", background: `color-mix(in srgb, ${color} 15%, transparent)`, color, border: `1px solid color-mix(in srgb, ${color} 25%, transparent)` }}
    >
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Notes timeline — parses `[YYYY-MM-DD HH:MM Name] body` entries and renders
// them as a vertical feed. Falls back to plain pre-wrap if no entries match
// (tickets created before timestamped-notes existed).
// ---------------------------------------------------------------------------

const NOTE_ENTRY_RE = /\[(\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?)\s*([^\]]*)\]\s*([\s\S]*?)(?=\n\[\d{4}-\d{2}-\d{2}|\s*$)/g

interface ParsedNote {
  when: string
  who: string
  body: string
}

function parseNotes(raw: string): ParsedNote[] | null {
  const out: ParsedNote[] = []
  let match: RegExpExecArray | null
  NOTE_ENTRY_RE.lastIndex = 0
  while ((match = NOTE_ENTRY_RE.exec(raw)) !== null) {
    const [, when, who, body] = match
    const text = body.trim()
    if (!text) continue
    out.push({ when: when.trim(), who: who.trim(), body: text })
  }
  return out.length > 0 ? out : null
}

function NotesTimeline({ raw }: { raw: string }) {
  const entries = useMemo(() => parseNotes(raw), [raw])
  if (!entries) {
    return (
      <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
        {raw}
      </p>
    )
  }
  return (
    <div
      className="mt-1 rounded overflow-hidden"
      style={{ border: "1px solid var(--color-border-subtle)", background: "var(--color-elevated)" }}
    >
      {entries.map((e, i) => (
        <div
          key={i}
          style={{
            padding: "6px 10px",
            borderBottom: i < entries.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
          }}
        >
          <div style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 10 }}>
            <span style={{ color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>{e.when}</span>
            {e.who && (
              <span style={{ color: "var(--color-lime)", fontWeight: 600 }}>{e.who}</span>
            )}
          </div>
          <p style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.5, marginTop: 2, whiteSpace: "pre-wrap" }}>
            {e.body}
          </p>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Quick-action bar — status-aware shortcuts that mirror the Streamlit app's
// QC Feedback, Verify This Change, and Review New Ticket surfaces. Each
// button is a one-click transition with an auto-generated note so users
// don't have to hand-write "Verified" every time.
// ---------------------------------------------------------------------------

interface QuickActionsProps {
  ticket: Ticket
  isAdmin: boolean
  busy: boolean
  onAction: (update: TicketUpdate) => Promise<void>
}

function TicketQuickActions({ ticket, isAdmin, busy, onAction }: QuickActionsProps) {
  const [qcNote, setQcNote] = useState("")
  const [rejectReason, setRejectReason] = useState("")

  const status = ticket.status
  const needsQc = ["New", "Approved", "In Progress"].includes(status)
  const canVerify = status === "In Review"
  const canApproveNew = status === "New" && isAdmin

  if (!needsQc && !canVerify && !canApproveNew) return null

  async function run(action: () => Promise<void>) {
    if (busy) return
    await action()
    setQcNote("")
    setRejectReason("")
  }

  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
      {/* QC Feedback */}
      {needsQc && (
        <div>
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 3, letterSpacing: "0.04em", textTransform: "uppercase" }}>
            QC Feedback
          </div>
          <input
            type="text"
            value={qcNote}
            onChange={e => setQcNote(e.target.value)}
            placeholder="Notes (optional)"
            className="w-full px-2 py-1.5 rounded text-xs mb-1.5"
            style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => run(() => onAction({
                status: "In Review",
                note: `QC passed${qcNote.trim() ? `: ${qcNote.trim()}` : ""}`,
              }))}
              disabled={busy}
              style={{
                flex: 1,
                padding: "5px 8px",
                fontSize: 11,
                fontWeight: 600,
                borderRadius: 3,
                background: "color-mix(in srgb, var(--color-ok) 12%, transparent)",
                color: "var(--color-ok)",
                border: "1px solid color-mix(in srgb, var(--color-ok) 28%, transparent)",
                cursor: busy ? "wait" : "pointer",
              }}
            >
              ✓ Fixed
            </button>
            <button
              onClick={() => run(() => onAction({
                note: `QC failed${qcNote.trim() ? `: ${qcNote.trim()}` : ""}`,
              }))}
              disabled={busy}
              style={{
                flex: 1,
                padding: "5px 8px",
                fontSize: 11,
                fontWeight: 600,
                borderRadius: 3,
                background: "color-mix(in srgb, var(--color-err) 10%, transparent)",
                color: "var(--color-err)",
                border: "1px solid color-mix(in srgb, var(--color-err) 25%, transparent)",
                cursor: busy ? "wait" : "pointer",
              }}
            >
              ✗ Still Broken
            </button>
          </div>
        </div>
      )}

      {/* Verify This Change */}
      {canVerify && (
        <div>
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 3, letterSpacing: "0.04em", textTransform: "uppercase" }}>
            Verify This Change
          </div>
          <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 6, lineHeight: 1.45 }}>
            Marked as done — confirm the fix landed, or reopen if not.
          </p>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => run(() => onAction({
                status: "Closed",
                note: "Verified — closing",
              }))}
              disabled={busy || !isAdmin}
              title={!isAdmin ? "Admins only can close tickets" : "Verify + close"}
              style={{
                flex: 1,
                padding: "5px 8px",
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 3,
                background: isAdmin ? "var(--color-lime)" : "var(--color-elevated)",
                color: isAdmin ? "var(--color-lime-ink)" : "var(--color-text-faint)",
                border: "1px solid " + (isAdmin ? "var(--color-lime)" : "var(--color-border)"),
                cursor: busy || !isAdmin ? "not-allowed" : "pointer",
              }}
            >
              Verified — Close
            </button>
            <button
              onClick={() => run(() => onAction({
                status: "In Progress",
                note: "Reopened — not fixed",
              }))}
              disabled={busy}
              style={{
                flex: 1,
                padding: "5px 8px",
                fontSize: 11,
                fontWeight: 600,
                borderRadius: 3,
                background: "transparent",
                color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
                cursor: busy ? "wait" : "pointer",
              }}
            >
              Not Fixed — Reopen
            </button>
          </div>
        </div>
      )}

      {/* Review New Ticket (admins only) */}
      {canApproveNew && (
        <div>
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 3, letterSpacing: "0.04em", textTransform: "uppercase" }}>
            Review New Ticket
          </div>
          <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
            <button
              onClick={() => run(() => onAction({
                status: "Approved",
                note: "Approved",
              }))}
              disabled={busy}
              style={{
                flex: 1,
                padding: "5px 8px",
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 3,
                background: "var(--color-lime)",
                color: "var(--color-lime-ink)",
                border: "1px solid var(--color-lime)",
                cursor: busy ? "wait" : "pointer",
              }}
            >
              Approve
            </button>
          </div>
          <input
            type="text"
            value={rejectReason}
            onChange={e => setRejectReason(e.target.value)}
            placeholder="Rejection reason (required)"
            className="w-full px-2 py-1.5 rounded text-xs mb-1.5"
            style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
          <button
            onClick={() => {
              if (!rejectReason.trim()) return
              return run(() => onAction({
                status: "Rejected",
                note: `Rejected: ${rejectReason.trim()}`,
              }))
            }}
            disabled={busy || !rejectReason.trim()}
            style={{
              width: "100%",
              padding: "5px 8px",
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 3,
              background: "color-mix(in srgb, var(--color-err) 10%, transparent)",
              color: rejectReason.trim() ? "var(--color-err)" : "var(--color-text-faint)",
              border: "1px solid color-mix(in srgb, var(--color-err) 25%, transparent)",
              cursor: busy ? "wait" : (!rejectReason.trim() ? "not-allowed" : "pointer"),
            }}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
