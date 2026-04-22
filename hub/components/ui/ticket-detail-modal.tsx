"use client"

import { useEffect, useMemo, useState } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import type { Ticket, TicketUpdate, UserProfile } from "@/lib/api"

/** Detail modal for a single ticket — replaces the cramped inline row
 *  expansion. Lifts the edit form (status/assignee/note), quick-action
 *  buttons (QC, Verify, Approve/Reject) and notes timeline out of the
 *  table so each gets the room it needs. Designed to match ShootModal
 *  chrome: portalled, blur backdrop, pinned header/footer, scrolling body. */
export function TicketDetailModal({
  ticket,
  users,
  isAdmin,
  saving,
  saveMsg,
  onClose,
  onQuickAction,
  onSave,
  initialEditStatus,
  initialEditAssignee,
}: {
  ticket: Ticket
  users: UserProfile[]
  isAdmin: boolean
  saving: boolean
  saveMsg: string | null
  onClose: () => void
  onQuickAction: (update: TicketUpdate) => Promise<void>
  onSave: (update: { status: string; assignee: string; note: string }) => Promise<void>
  initialEditStatus: string
  initialEditAssignee: string
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  const [editStatus, setEditStatus] = useState(initialEditStatus)
  const [editAssignee, setEditAssignee] = useState(initialEditAssignee)
  const [editNote, setEditNote] = useState("")
  const [qcNote, setQcNote] = useState("")
  const [rejectReason, setRejectReason] = useState("")

  // Reset edit state when the ticket identity changes (modal reuse).
  useEffect(() => {
    setEditStatus(initialEditStatus)
    setEditAssignee(initialEditAssignee)
    setEditNote("")
  }, [ticket.ticket_id, initialEditStatus, initialEditAssignee])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  const priColor = PRIORITY_COLOR[ticket.priority] ?? "var(--color-text-muted)"
  const statColor = STATUS_COLOR[ticket.status] ?? "var(--color-text-muted)"

  const needsQc = ["New", "Approved", "In Progress"].includes(ticket.status)
  const canVerify = ticket.status === "In Review"
  const canApproveNew = ticket.status === "New" && isAdmin
  const hasQuickActions = needsQc || canVerify || canApproveNew

  const parsedNotes = useMemo(() => parseNotes(ticket.notes || ""), [ticket.notes])

  if (!mounted) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ticket-modal-title"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0, 0, 0, 0.72)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fadeIn var(--duration-base) var(--ease-out-expo) both",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(760px, 100%)",
          maxHeight: "min(90vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
          minHeight: 0,
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--color-border)",
            flexShrink: 0,
          }}
        >
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--color-text-faint)",
                marginBottom: 6,
              }}
            >
              {ticket.ticket_id}
              {ticket.project && (
                <span style={{ color: "var(--color-text-muted)" }}> · {ticket.project}</span>
              )}
              {ticket.type && (
                <span style={{ color: "var(--color-text-muted)" }}> · {ticket.type}</span>
              )}
            </div>
            <h2
              id="ticket-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 800,
                fontSize: 24,
                lineHeight: 1.15,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              {ticket.title}
            </h2>
            <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              <Badge label={ticket.status} color={statColor} />
              <Badge label={ticket.priority} color={priColor} />
              {ticket.submitted_at && (
                <span style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                  {formatDate(ticket.submitted_at)}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 18, overflowY: "auto", flex: "1 1 auto", minHeight: 0 }}>
          {ticket.description && (
            <section style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <SectionLabel>Description</SectionLabel>
              <p style={{ fontSize: 13, color: "var(--color-text)", lineHeight: 1.65, whiteSpace: "pre-wrap", margin: 0 }}>
                {ticket.description}
              </p>
            </section>
          )}

          {(ticket.submitted_by || ticket.assignee || ticket.linked_items || ticket.resolved_at) && (
            <section style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <SectionLabel>Metadata</SectionLabel>
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 12, rowGap: 4, fontSize: 12 }}>
                {ticket.submitted_by && <MetaRow label="Reporter" value={ticket.submitted_by} />}
                {ticket.assignee && <MetaRow label="Assignee" value={ticket.assignee} />}
                {ticket.linked_items && <MetaRow label="Linked" value={ticket.linked_items} mono />}
                {ticket.resolved_at && <MetaRow label="Resolved" value={formatDate(ticket.resolved_at)} />}
              </div>
            </section>
          )}

          {parsedNotes && parsedNotes.length > 0 ? (
            <section style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <SectionLabel>Notes</SectionLabel>
              <div style={{ border: "1px solid var(--color-border-subtle)", background: "var(--color-elevated)" }}>
                {parsedNotes.map((n, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "8px 12px",
                      borderBottom: i < parsedNotes.length - 1 ? "1px solid var(--color-border-subtle)" : undefined,
                    }}
                  >
                    <div style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 10 }}>
                      <span style={{ color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>{n.when}</span>
                      {n.who && <span style={{ color: "var(--color-lime)", fontWeight: 600 }}>{n.who}</span>}
                    </div>
                    <p style={{ fontSize: 12, color: "var(--color-text)", lineHeight: 1.5, marginTop: 3, whiteSpace: "pre-wrap" }}>{n.body}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : ticket.notes ? (
            <section style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <SectionLabel>Notes</SectionLabel>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.55, whiteSpace: "pre-wrap", margin: 0 }}>{ticket.notes}</p>
            </section>
          ) : null}

          {hasQuickActions && (
            <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <SectionLabel>Quick actions</SectionLabel>
              {needsQc && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <input
                    type="text"
                    value={qcNote}
                    onChange={e => setQcNote(e.target.value)}
                    placeholder="QC note (optional)"
                    style={inputStyle}
                  />
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => onQuickAction({ status: "In Review", note: `QC passed${qcNote.trim() ? `: ${qcNote.trim()}` : ""}` }).then(() => setQcNote(""))}
                      style={actionButtonStyle("var(--color-ok)")}
                    >
                      ✓ Fixed
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => onQuickAction({ note: `QC failed${qcNote.trim() ? `: ${qcNote.trim()}` : ""}` }).then(() => setQcNote(""))}
                      style={actionButtonStyle("var(--color-err)")}
                    >
                      ✗ Still Broken
                    </button>
                  </div>
                </div>
              )}
              {canVerify && (
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    type="button"
                    disabled={saving || !isAdmin}
                    title={!isAdmin ? "Admins only" : "Verify + close"}
                    onClick={() => onQuickAction({ status: "Closed", note: "Verified — closing" })}
                    style={{
                      ...actionButtonStyle("var(--color-lime)"),
                      background: isAdmin ? "var(--color-lime)" : "var(--color-elevated)",
                      color: isAdmin ? "var(--color-lime-ink)" : "var(--color-text-faint)",
                      fontWeight: 700,
                    }}
                  >
                    Verified — Close
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => onQuickAction({ status: "In Progress", note: "Reopened — not fixed" })}
                    style={{
                      ...actionButtonStyle("var(--color-border)"),
                      background: "transparent",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    Not Fixed — Reopen
                  </button>
                </div>
              )}
              {canApproveNew && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => onQuickAction({ status: "Approved", note: "Approved" })}
                    style={{
                      ...actionButtonStyle("var(--color-lime)"),
                      background: "var(--color-lime)",
                      color: "var(--color-lime-ink)",
                      fontWeight: 700,
                    }}
                  >
                    Approve
                  </button>
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    placeholder="Rejection reason (required)"
                    style={inputStyle}
                  />
                  <button
                    type="button"
                    disabled={saving || !rejectReason.trim()}
                    onClick={() => onQuickAction({ status: "Rejected", note: `Rejected: ${rejectReason.trim()}` }).then(() => setRejectReason(""))}
                    style={{
                      ...actionButtonStyle("var(--color-err)"),
                      opacity: rejectReason.trim() ? 1 : 0.5,
                      cursor: rejectReason.trim() ? "pointer" : "not-allowed",
                    }}
                  >
                    Reject
                  </button>
                </div>
              )}
            </section>
          )}

          <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <SectionLabel>Edit</SectionLabel>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={editLabelStyle}>Status</label>
                <select
                  value={editStatus}
                  onChange={e => setEditStatus(e.target.value)}
                  style={inputStyle}
                >
                  {TICKET_STATUSES.map(s => {
                    const isLocked = !isAdmin && ADMIN_ONLY_STATUSES.has(s) && s !== ticket.status
                    return <option key={s} value={s} disabled={isLocked}>{s}{isLocked ? " — admin only" : ""}</option>
                  })}
                </select>
              </div>
              <div>
                <label style={editLabelStyle}>Assignee</label>
                {users.length > 0 ? (
                  <select
                    value={editAssignee}
                    onChange={e => setEditAssignee(e.target.value)}
                    style={inputStyle}
                  >
                    <option value="">Unassigned</option>
                    {users.map(u => <option key={u.email} value={u.name}>{u.name}</option>)}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={editAssignee}
                    onChange={e => setEditAssignee(e.target.value)}
                    placeholder="Name or email"
                    style={inputStyle}
                  />
                )}
              </div>
            </div>
            <div>
              <label style={editLabelStyle}>Add note</label>
              <textarea
                value={editNote}
                onChange={e => setEditNote(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="Optional update note…"
                style={{ ...inputStyle, resize: "vertical", minHeight: 70 }}
              />
            </div>
          </section>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            flexShrink: 0,
            background: "var(--color-surface)",
          }}
        >
          <span
            role={saveMsg ? "status" : undefined}
            aria-live="polite"
            style={{
              fontSize: 11,
              color: !saveMsg
                ? "transparent"
                : saveMsg === "Saved."
                  ? "var(--color-ok)"
                  : saveMsg === "No changes."
                    ? "var(--color-text-muted)"
                    : "var(--color-err)",
            }}
          >
            {saveMsg ?? "·"}
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "6px 14px",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                background: "transparent",
                color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
                cursor: "pointer",
              }}
            >
              Close
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => onSave({ status: editStatus, assignee: editAssignee, note: editNote })}
              style={{
                padding: "6px 14px",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                background: "var(--color-lime)",
                color: "var(--color-lime-ink)",
                border: "1px solid var(--color-lime)",
                cursor: saving ? "wait" : "pointer",
                opacity: saving ? 0.6 : 1,
              }}
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// ---------------------------------------------------------------------------
// Shared constants — kept local so the modal is self-contained and the
// ticket-list can import only what it renders inline.
// ---------------------------------------------------------------------------

const TICKET_STATUSES = ["New", "Approved", "In Progress", "In Review", "Closed", "Rejected"]
const ADMIN_ONLY_STATUSES = new Set(["Closed", "Rejected"])

const PRIORITY_COLOR: Record<string, string> = {
  Critical: "var(--color-err)",
  High: "var(--color-njoi)",
  Medium: "var(--color-warn)",
  Low: "var(--color-text-muted)",
}

const STATUS_COLOR: Record<string, string> = {
  "New": "var(--color-text)",
  "Approved": "var(--color-ok)",
  "In Progress": "var(--color-fpvr)",
  "In Review": "var(--color-lime)",
  "Closed": "var(--color-text-faint)",
  "Rejected": "var(--color-err)",
}

const DATE_FMT = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" })

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return DATE_FMT.format(d)
}

const NOTE_ENTRY_RE = /\[(\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?)\s*([^\]]*)\]\s*([\s\S]*?)(?=\n\[\d{4}-\d{2}-\d{2}|\s*$)/g

interface ParsedNote { when: string; who: string; body: string }

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

// ---------------------------------------------------------------------------
// Tiny style helpers
// ---------------------------------------------------------------------------

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 10px",
  fontSize: 12,
  background: "var(--color-elevated)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text)",
  outline: "none",
}

const editLabelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: "0.16em",
  textTransform: "uppercase",
  color: "var(--color-text-faint)",
}

function actionButtonStyle(color: string): React.CSSProperties {
  return {
    flex: 1,
    padding: "6px 10px",
    fontSize: 11,
    fontWeight: 600,
    background: `color-mix(in srgb, ${color} 12%, transparent)`,
    color,
    border: `1px solid color-mix(in srgb, ${color} 28%, transparent)`,
    cursor: "pointer",
  }
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 7px",
        fontSize: 10,
        fontWeight: 600,
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

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--color-text-faint)",
      }}
    >
      {children}
    </div>
  )
}

function MetaRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <>
      <span style={{ color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase", fontSize: 9, fontWeight: 700, alignSelf: "center" }}>
        {label}
      </span>
      <span style={{ color: "var(--color-text)", fontFamily: mono ? "var(--font-mono)" : undefined, fontSize: mono ? 11 : 12 }}>
        {value}
      </span>
    </>
  )
}
