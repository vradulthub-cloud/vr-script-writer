"use client"

import { useState, useMemo } from "react"
import type { Ticket, TicketUpdate } from "@/lib/api"
import { studiosFromTicket } from "./ticket-utils"

// ---------------------------------------------------------------------------
// StudioCellChips
// ---------------------------------------------------------------------------

/**
 * Per-row studio chips. Reuses studiosFromTicket so the column always
 * agrees with the studio filter — there's never a row visible under
 * "VRH" that doesn't show a VRH chip here. Renders nothing for tickets
 * with no scene linkage so the column doesn't get noisy.
 */
export function StudioCellChips({ ticket }: { ticket: Ticket }) {
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

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

export function Badge({ label, color }: { label: string; color: string }) {
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

export function NotesTimeline({ raw }: { raw: string }) {
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

export function TicketQuickActions({ ticket, isAdmin, busy, onAction }: QuickActionsProps) {
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
            aria-label="QC feedback notes"
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
            aria-label="Rejection reason"
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
