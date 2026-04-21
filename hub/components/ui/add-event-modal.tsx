"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import type { CalendarEvent } from "@/lib/calendar-events"

/** Small modal to capture a new calendar event. Portalled to body so the
 *  existing shoots-page fadeIn transform doesn't trap the fixed overlay. */
export function AddEventModal({
  date,
  onSave,
  onClose,
}: {
  date: string
  onSave: (ev: Omit<CalendarEvent, "id">) => void
  onClose: () => void
}) {
  const [title, setTitle] = useState("")
  const [kind, setKind] = useState("")
  const [notes, setNotes] = useState("")
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const prettyDate = new Date(date + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) return
    onSave({ date, title: trimmed, kind: kind.trim() || undefined, notes: notes.trim() || undefined })
    onClose()
  }

  if (!mounted) return null

  return createPortal(
    <div
      role="dialog"
      aria-label="Add event"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.55)",
        zIndex: 1200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <form
        onClick={e => e.stopPropagation()}
        onSubmit={submit}
        style={{
          width: "min(440px, 100%)",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <header
          style={{
            padding: "14px 16px",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
          }}
        >
          <div>
            <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
              New Event
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>
              {prettyDate}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              fontSize: 14,
              lineHeight: 1,
              padding: "4px 8px",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </header>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
              Title
            </span>
            <input
              autoFocus
              required
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Call with agency"
              style={inputStyle}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
              Kind <span style={{ color: "var(--color-text-faint)" }}>(optional · short tag)</span>
            </span>
            <input
              value={kind}
              onChange={e => setKind(e.target.value)}
              placeholder="MEETING · TRAVEL · DEADLINE"
              style={inputStyle}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
              Notes <span style={{ color: "var(--color-text-faint)" }}>(optional)</span>
            </span>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              style={{ ...inputStyle, resize: "vertical" }}
            />
          </label>
        </div>
        <footer
          style={{
            padding: "12px 16px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "6px 14px",
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim()}
            style={{
              padding: "6px 14px",
              background: "var(--color-lime)",
              border: "1px solid var(--color-lime)",
              color: "var(--color-lime-ink, #0d0d0d)",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              cursor: title.trim() ? "pointer" : "not-allowed",
              opacity: title.trim() ? 1 : 0.5,
            }}
          >
            Save
          </button>
        </footer>
      </form>
    </div>,
    document.body,
  )
}

const inputStyle: React.CSSProperties = {
  background: "var(--color-elevated)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text)",
  fontSize: 13,
  padding: "8px 10px",
  outline: "none",
  fontFamily: "inherit",
}
