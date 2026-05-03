"use client"

import { useState } from "react"

/**
 * Letterhead — centered eyebrow + rule + title + optional subtitle. Used at
 * the top of every paper-themed step (Form, Review, Sign, Success). Mirrors
 * the v2 design's print-document feel.
 */
export function Letterhead({
  title,
  subtitle,
  eyebrow = "Eclatech LLC",
}: {
  title: string
  subtitle?: string | null
  eyebrow?: string
}) {
  return (
    <div style={{ textAlign: "center", padding: "32px 20px 20px" }}>
      <div className="doc-letterhead-eyebrow">{eyebrow}</div>
      <div className="doc-letterhead-rule" />
      <h1 className="doc-letterhead-title">{title}</h1>
      {subtitle && <div className="doc-letterhead-sub">{subtitle}</div>}
    </div>
  )
}

/**
 * LockBanner — sticky top bar shown while talent is in the paperwork flow.
 * Communicates "Document Mode — Navigation locked" and provides a hidden
 * crew-unlock PIN field (default 0000). Calling onUnlock exits the wizard
 * back to the shoot list. Renders above the compliance-paper surface.
 */
export function LockBanner({
  onUnlock,
  pin = "0000",
}: {
  onUnlock: () => void
  pin?: string
}) {
  const [open, setOpen] = useState(false)
  const [entered, setEntered] = useState("")
  const [err, setErr] = useState(false)
  function tryUnlock() {
    if (entered === pin) onUnlock()
    else {
      setErr(true)
      setEntered("")
      setTimeout(() => setErr(false), 1200)
    }
  }
  return (
    <div className="compliance-lock-banner">
      <span className="lock-label">🔒 DOCUMENT MODE — Navigation locked</span>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{
            fontSize: 10,
            color: "#999",
            background: "none",
            border: "1px solid #444",
            borderRadius: 4,
            padding: "2px 10px",
            cursor: "pointer",
            fontFamily: "var(--font-sans)",
          }}
        >
          Crew unlock
        </button>
      ) : (
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <input
            type="password"
            inputMode="numeric"
            maxLength={4}
            value={entered}
            onChange={e => setEntered(e.target.value.replace(/\D/g, ""))}
            onKeyDown={e => e.key === "Enter" && tryUnlock()}
            autoFocus
            placeholder="PIN"
            className="lock-pin-input"
            style={err ? { borderColor: "#e44" } : undefined}
          />
          <button
            type="button"
            onClick={tryUnlock}
            style={{
              fontSize: 10,
              background: "#d4a017",
              color: "#000",
              border: "none",
              borderRadius: 4,
              padding: "3px 8px",
              cursor: "pointer",
              fontWeight: 700,
              fontFamily: "var(--font-sans)",
            }}
          >
            OK
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              setEntered("")
            }}
            style={{
              fontSize: 12,
              color: "#888",
              background: "none",
              border: "none",
              cursor: "pointer",
            }}
            aria-label="Cancel unlock"
          >
            ×
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * SuccessSeal — circular green stamp used by the Success step. Animates in
 * with the doc-stamp keyframe (defined in globals.css under .compliance-paper).
 */
export function SuccessSeal() {
  return (
    <div
      className="doc-stamp"
      style={{
        width: 80,
        height: 80,
        borderRadius: "50%",
        border: "2px solid #1a5c3a",
        background: "#eaf4ee",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        margin: "0 auto 24px",
      }}
    >
      <span style={{ fontSize: 36, color: "#1a5c3a", lineHeight: 1 }}>✓</span>
    </div>
  )
}
