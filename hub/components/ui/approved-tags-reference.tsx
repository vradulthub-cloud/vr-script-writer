"use client"

import { useState } from "react"
import { STUDIO_TAGS, type StudioKey } from "@/lib/studio-tags"

/**
 * Collapsible reference panel for a studio's approved tag allow-list.
 * Mirrors the Streamlit UX: a tiny disclosure under the form that
 * expands to a long comma-separated string. Used in Descriptions + the
 * Missing-Assets Tags editor so editors don't have to alt-tab to the
 * Grail sheet.
 *
 * Returns null for studios with no allow-list (NaughtyJOI).
 */
export function ApprovedTagsReference({ studio }: { studio: string }) {
  const [open, setOpen] = useState(false)
  const tags = STUDIO_TAGS[studio as StudioKey] ?? ""
  if (!tags) return null

  return (
    <div
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: 4,
        background: "var(--color-surface)",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          width: "100%",
          padding: "6px 10px",
          background: "transparent",
          border: "none",
          color: "var(--color-text-muted)",
          fontSize: 11,
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span aria-hidden style={{ fontSize: 9, color: "var(--color-text-faint)", transform: open ? "rotate(90deg)" : undefined, transition: "transform 150ms" }}>
          ▶
        </span>
        Approved {studio} Tags Reference
      </button>
      {open && (
        <div
          style={{
            padding: "6px 10px 10px",
            fontSize: 10,
            color: "var(--color-text-faint)",
            lineHeight: 1.55,
            maxHeight: 180,
            overflow: "auto",
            borderTop: "1px solid var(--color-border-subtle)",
          }}
        >
          {tags}
        </div>
      )}
    </div>
  )
}
