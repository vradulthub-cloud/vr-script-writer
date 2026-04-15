"use client"

import { useState, useMemo } from "react"
import { ErrorAlert } from "@/components/ui/error-alert"
import { api, type Ticket, type TicketCreate, type TicketUpdate } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"

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

const STATUSES = ["All", "New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
const TICKET_STATUSES = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
const PRIORITIES = ["Low", "Medium", "High", "Critical"]
const PROJECTS = ["", "Hub", "Content", "Infrastructure", "Scripts", "Descriptions", "MEGA", "Other"]
const TYPES = ["", "Bug", "Feature", "Task", "Question", "Improvement"]

interface Props {
  tickets: Ticket[]
  error: string | null
  idToken: string | undefined
}

export function TicketList({ tickets: initialTickets, error, idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [tickets, setTickets] = useState<Ticket[]>(initialTickets)
  const [statusFilter, setStatusFilter] = useState("All")
  const [expanded, setExpanded] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  // Editing state for the expanded row
  const [editStatus, setEditStatus] = useState("")
  const [editAssignee, setEditAssignee] = useState("")
  const [editNote, setEditNote] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)

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

  const filtered = useMemo(
    () =>
      statusFilter === "All"
        ? tickets
        : tickets.filter((t) => t.status === statusFilter),
    [tickets, statusFilter]
  )

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

  async function saveUpdate(ticketId: string) {
    setSaving(true)
    setSaveMsg(null)
    const body: TicketUpdate = {}
    const ticket = tickets.find(t => t.ticket_id === ticketId)
    if (!ticket) return
    if (editStatus !== ticket.status) body.status = editStatus
    if (editAssignee !== ticket.assignee) body.assignee = editAssignee
    if (editNote.trim()) body.note = editNote.trim()
    if (Object.keys(body).length === 0) { setSaving(false); setSaveMsg("No changes."); return }
    try {
      const updated = await client.tickets.update(ticketId, body)
      setTickets(prev => prev.map(t => t.ticket_id === ticketId ? updated : t))
      setSaveMsg("Saved.")
      setEditNote("")
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed")
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
    } catch (e) {
      setCreateErr(e instanceof Error ? e.message : "Create failed")
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      {/* Filter bar + new ticket button */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex gap-1 flex-wrap">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="px-2.5 py-1 rounded text-xs transition-colors"
              style={{
                background: statusFilter === s ? "var(--color-elevated)" : "transparent",
                color: statusFilter === s ? "var(--color-text)" : "var(--color-text-muted)",
                border: `1px solid ${statusFilter === s ? "var(--color-border)" : "transparent"}`,
              }}
            >
              {s}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
          style={{ background: "var(--color-lime)", color: "#0d0d0d" }}
        >
          + New Ticket
        </button>
      </div>

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
      {!error && filtered.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
          No tickets{statusFilter !== "All" ? ` with status "${statusFilter}"` : ""}.
        </p>
      )}

      {/* Table */}
      {!error && filtered.length > 0 && (
        <div className="rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
          <table className="w-full" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                {["ID", "Title", "Project", "Priority", "Status", "By", "Date"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2 font-medium"
                    style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((ticket, i) => {
                const isExpanded = expanded === ticket.ticket_id
                const isLast = i === filtered.length - 1
                return (
                  <>
                    <tr
                      key={ticket.ticket_id}
                      className="transition-colors cursor-pointer"
                      onClick={() => openTicket(ticket)}
                      style={{
                        borderBottom: !isExpanded && !isLast ? "1px solid var(--color-border-subtle)" : undefined,
                        background: isExpanded ? "var(--color-surface)" : undefined,
                      }}
                      onMouseEnter={e => { if (!isExpanded) (e.currentTarget as HTMLElement).style.background = "var(--color-elevated)" }}
                      onMouseLeave={e => { if (!isExpanded) (e.currentTarget as HTMLElement).style.background = "" }}
                    >
                      <td className="px-3 py-2.5 font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                        {ticket.ticket_id}
                      </td>
                      <td className="px-3 py-2.5" style={{ fontSize: 12, maxWidth: 320 }}>
                        <span className="line-clamp-1">{ticket.title}</span>
                        {ticket.description && (
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
                        key={`${ticket.ticket_id}-detail`}
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
                                <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6, lineHeight: 1.5 }}>
                                  {ticket.notes}
                                </p>
                              )}
                            </div>

                            {/* Right: edit panel */}
                            <div style={{ width: 260, flexShrink: 0 }}>
                              <div className="flex flex-col gap-2">
                                <div>
                                  <label style={{ fontSize: 10, color: "var(--color-text-faint)", display: "block", marginBottom: 3 }}>STATUS</label>
                                  <select
                                    value={editStatus}
                                    onChange={e => setEditStatus(e.target.value)}
                                    className="w-full px-2 py-1.5 rounded text-xs outline-none"
                                    style={{
                                      background: "var(--color-elevated)",
                                      border: "1px solid var(--color-border)",
                                      color: STATUS_COLOR[editStatus] ?? "var(--color-text)",
                                    }}
                                  >
                                    {TICKET_STATUSES.map(s => (
                                      <option key={s} value={s}>{s}</option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label style={{ fontSize: 10, color: "var(--color-text-faint)", display: "block", marginBottom: 3 }}>ASSIGNEE</label>
                                  <input
                                    type="text"
                                    value={editAssignee}
                                    onChange={e => setEditAssignee(e.target.value)}
                                    placeholder="Name or email"
                                    className="w-full px-2 py-1.5 rounded text-xs outline-none"
                                    style={{
                                      background: "var(--color-elevated)",
                                      border: "1px solid var(--color-border)",
                                      color: "var(--color-text)",
                                    }}
                                  />
                                </div>
                                <div>
                                  <label style={{ fontSize: 10, color: "var(--color-text-faint)", display: "block", marginBottom: 3 }}>ADD NOTE</label>
                                  <textarea
                                    value={editNote}
                                    onChange={e => setEditNote(e.target.value)}
                                    rows={2}
                                    placeholder="Optional update note…"
                                    className="w-full px-2 py-1.5 rounded text-xs outline-none resize-none"
                                    style={{
                                      background: "var(--color-elevated)",
                                      border: "1px solid var(--color-border)",
                                      color: "var(--color-text)",
                                    }}
                                  />
                                </div>
                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={() => saveUpdate(ticket.ticket_id)}
                                    disabled={saving}
                                    className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                                    style={{
                                      background: "var(--color-lime)",
                                      color: "#0d0d0d",
                                      opacity: saving ? 0.5 : 1,
                                    }}
                                  >
                                    {saving ? "Saving…" : "Save Changes"}
                                  </button>
                                  {saveMsg && (
                                    <span style={{ fontSize: 11, color: saveMsg === "Saved." ? "var(--color-ok)" : saveMsg === "No changes." ? "var(--color-text-muted)" : "var(--color-err)" }}>
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
                  </>
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
          style={{ background: "rgba(0,0,0,0.6)", zIndex: 50 }}
          onClick={e => { if (e.target === e.currentTarget) setShowCreate(false) }}
        >
          <div
            className="rounded-lg"
            style={{
              background: "var(--color-base)",
              border: "1px solid var(--color-border)",
              width: 480,
              maxWidth: "calc(100vw - 32px)",
              padding: "20px 24px",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>New Ticket</h2>
              <button
                onClick={() => setShowCreate(false)}
                style={{ fontSize: 18, color: "var(--color-text-muted)", lineHeight: 1, padding: "0 4px" }}
              >
                ×
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <div>
                <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Title *</label>
                <input
                  type="text"
                  value={createForm.title}
                  onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="Short summary of the issue or request"
                  autoFocus
                  className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Description</label>
                <textarea
                  value={createForm.description}
                  onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))}
                  rows={3}
                  placeholder="Steps to reproduce, expected behavior, context…"
                  className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
              </div>

              <div className="flex gap-3">
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Project</label>
                  <select
                    value={createForm.project}
                    onChange={e => setCreateForm(f => ({ ...f, project: e.target.value }))}
                    className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      color: createForm.project ? "var(--color-text)" : "var(--color-text-muted)",
                    }}
                  >
                    {PROJECTS.map(p => <option key={p} value={p}>{p || "— Select —"}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Type</label>
                  <select
                    value={createForm.type}
                    onChange={e => setCreateForm(f => ({ ...f, type: e.target.value }))}
                    className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      color: createForm.type ? "var(--color-text)" : "var(--color-text-muted)",
                    }}
                  >
                    {TYPES.map(t => <option key={t} value={t}>{t || "— Select —"}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Priority</label>
                  <select
                    value={createForm.priority}
                    onChange={e => setCreateForm(f => ({ ...f, priority: e.target.value }))}
                    className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      color: PRIORITY_COLOR[createForm.priority ?? "Medium"] ?? "var(--color-text)",
                    }}
                  >
                    {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Linked items</label>
                <input
                  type="text"
                  value={createForm.linked_items}
                  onChange={e => setCreateForm(f => ({ ...f, linked_items: e.target.value }))}
                  placeholder="Scene IDs, ticket IDs, etc."
                  className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
              </div>
            </div>

            {createErr && <ErrorAlert className="mt-3 text-xs">{createErr}</ErrorAlert>}

            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowCreate(false)}
                className="px-3 py-1.5 rounded text-xs transition-colors"
                style={{
                  background: "transparent",
                  color: "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                Cancel
              </button>
              <button
                onClick={createTicket}
                disabled={creating || !createForm.title.trim()}
                className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                style={{
                  background: "var(--color-lime)",
                  color: "#0d0d0d",
                  opacity: (creating || !createForm.title.trim()) ? 0.5 : 1,
                  cursor: (creating || !createForm.title.trim()) ? "not-allowed" : "pointer",
                }}
              >
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
      style={{
        fontSize: 10,
        fontWeight: 500,
        letterSpacing: "0.02em",
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      {label}
    </span>
  )
}
