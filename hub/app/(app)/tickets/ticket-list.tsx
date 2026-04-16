"use client"

import React, { useState, useMemo, useEffect, useRef } from "react"
import { X, ChevronRight, ChevronDown, Search } from "lucide-react"
import { ErrorAlert } from "@/components/ui/error-alert"
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
  { key: "New",         label: "NEW",         color: "var(--color-text)" },
  { key: "Approved",    label: "APPROVED",    color: "var(--color-ok)" },
  { key: "In Progress", label: "IN PROGRESS", color: "var(--color-fpvr)" },
  { key: "In Review",   label: "IN REVIEW",   color: "var(--color-lime)" },
  { key: "Closed",      label: "CLOSED",      color: "var(--color-text-faint)" },
  { key: "Rejected",    label: "REJECTED",    color: "var(--color-err)" },
] as const

const TICKET_STATUSES = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
const PRIORITIES = ["Low", "Medium", "High", "Critical"]
const PRIORITY_ORDER = ["Critical", "High", "Medium", "Low"]
const STATUS_ORDER = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
const PROJECTS = ["", "Hub", "Content", "Infrastructure", "Scripts", "Descriptions", "MEGA", "Other"]
const TYPES = ["", "Bug", "Feature", "Task", "Question", "Improvement"]

type SortKey = "date" | "priority" | "status"

const COLUMNS: { key: string; label: string; sort?: SortKey }[] = [
  { key: "id", label: "ID" },
  { key: "title", label: "Title" },
  { key: "project", label: "Project" },
  { key: "priority", label: "Priority", sort: "priority" },
  { key: "status", label: "Status", sort: "status" },
  { key: "submitted", label: "Submitted" },
  { key: "date", label: "Date", sort: "date" },
]

interface Props {
  tickets: Ticket[]
  users: UserProfile[]
  error: string | null
  idToken: string | undefined
}

export function TicketList({ tickets: initialTickets, users, error, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [tickets, setTickets] = useState<Ticket[]>(initialTickets)
  const [statusFilter, setStatusFilter] = useState("All")
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

  // Create form state
  const [createForm, setCreateForm] = useState<TicketCreate>({
    title: "",
    description: "",
    project: "",
    type: "",
    priority: "Medium",
    linked_items: "",
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

  const displayTickets = useMemo(() => {
    let result = statusFilter === "All" ? tickets : tickets.filter(t => t.status === statusFilter)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
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
  }, [tickets, statusFilter, searchQuery, sortKey, sortDir])

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

  async function saveUpdate(ticketId: string) {
    setSaving(true)
    setSaveMsg(null)
    const body: TicketUpdate = {}
    const ticket = tickets.find(t => t.ticket_id === ticketId)
    if (!ticket) { setSaving(false); return }
    if (editStatus !== ticket.status) body.status = editStatus
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
      setCreateForm({ title: "", description: "", project: "", type: "", priority: "Medium", linked_items: "" })
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
      {/* Stat filter cards */}
      {!error && (
        <div className="flex items-end justify-between mb-4 gap-3 flex-wrap">
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setStatusFilter("All")}
              aria-pressed={statusFilter === "All"}
              className="rounded px-3 py-2 transition-colors text-left"
              style={{
                background: statusFilter === "All" ? "var(--color-elevated)" : "var(--color-surface)",
                border: `1px solid ${statusFilter === "All" ? "var(--color-lime)" : "var(--color-border)"}`,
                minWidth: 56,
              }}
            >
              <p className="font-bold tabular-nums" style={{ fontSize: 24, color: "var(--color-text)", lineHeight: 1, letterSpacing: "-0.02em" }}>
                {tickets.length}
              </p>
              <p style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 3, fontWeight: 500, letterSpacing: "0.04em" }}>
                ALL
              </p>
            </button>
            {STAT_CONFIGS.map(({ key, label, color }) => {
              const count = counts[key] ?? 0
              const isActive = statusFilter === key
              return (
                <button
                  key={key}
                  onClick={() => setStatusFilter(key)}
                  aria-pressed={isActive}
                  className="rounded px-3 py-2 transition-colors text-left"
                  style={{
                    background: isActive
                      ? `color-mix(in srgb, ${color} 12%, var(--color-surface))`
                      : count > 0 ? `color-mix(in srgb, ${color} 6%, var(--color-surface))` : "var(--color-surface)",
                    border: `1px solid ${
                      isActive
                        ? `color-mix(in srgb, ${color} 45%, transparent)`
                        : count > 0 ? `color-mix(in srgb, ${color} 20%, transparent)` : "var(--color-border)"
                    }`,
                    minWidth: 56,
                    opacity: count === 0 ? 0.45 : 1,
                  }}
                >
                  <p className="font-bold tabular-nums" style={{ fontSize: 24, color, lineHeight: 1, letterSpacing: "-0.02em" }}>
                    {count}
                  </p>
                  <p style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 3, fontWeight: 500, letterSpacing: "0.04em" }}>
                    {label}
                  </p>
                </button>
              )
            })}
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
            style={{ background: "var(--color-lime)", color: "var(--color-base)" }}
          >
            + New Ticket
          </button>
        </div>
      )}

      {/* Search */}
      {!error && tickets.length > 0 && (
        <div className="relative mb-3">
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
              maxWidth: 360,
            }}
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
              : statusFilter !== "All"
                ? `No tickets with status "${statusFilter}"`
                : "No tickets yet"}
          </p>
          {statusFilter === "All" && !searchQuery.trim() && (
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

      {/* Table */}
      {!error && displayTickets.length > 0 && (
        <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
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
                      <td className="px-3 py-2.5" style={{ fontSize: 12, maxWidth: 320 }}>
                        <span className="line-clamp-1">{ticket.title}</span>
                        {!isExpanded && ticket.description && (
                          <span
                            className="block line-clamp-1 mt-0.5"
                            style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                          >
                            {ticket.description}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                        {ticket.project || "—"}
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <Badge label={ticket.priority} color={PRIORITY_COLOR[ticket.priority] ?? "var(--color-text-muted)"} />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <Badge label={ticket.status} color={STATUS_COLOR[ticket.status] ?? "var(--color-text-muted)"} />
                      </td>
                      <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                        {ticket.submitted_by || "—"}
                      </td>
                      <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                        {ticket.submitted_at ? ticket.submitted_at.slice(0, 10) : "—"}
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
                                {ticket.type && (
                                  <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                    Type: <span style={{ color: "var(--color-text)" }}>{ticket.type}</span>
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
                                    Resolved: <span style={{ color: "var(--color-text)" }}>{ticket.resolved_at.slice(0, 10)}</span>
                                  </span>
                                )}
                              </div>
                              {ticket.notes && (
                                <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                                  {ticket.notes}
                                </p>
                              )}
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
                                    {TICKET_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
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
                <textarea id="create-description" value={createForm.description} onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))} rows={3} placeholder="Steps to reproduce, expected behavior, context…" className="w-full px-2.5 py-1.5 rounded text-xs resize-none" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
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
              <div>
                <label htmlFor="create-linked" style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Linked items <span style={{ color: "var(--color-text-faint)" }}>(scene IDs, ticket IDs)</span></label>
                <input id="create-linked" type="text" value={createForm.linked_items} onChange={e => setCreateForm(f => ({ ...f, linked_items: e.target.value }))} placeholder="e.g. TKT-0012, SC-1234" className="w-full px-2.5 py-1.5 rounded text-xs" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
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
