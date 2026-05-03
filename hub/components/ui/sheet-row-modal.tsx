"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import type { Script } from "@/lib/api"
import { studioAbbr, studioColor } from "@/lib/studio-colors"

/** Overwrite-confirmation modal shown in Scripts/"From Sheet" when the user
 *  has unsaved manual inputs and a row-select would clobber them. Replaces
 *  the inline yellow banner with a focused prompt that previews the row
 *  you're about to load. */
export function SheetRowModal({
  row,
  currentFemale,
  currentMale,
  onConfirm,
  onCancel,
}: {
  row: Script
  currentFemale: string
  currentMale: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onCancel])

  if (!mounted) return null

  const color = studioColor(row.studio)
  const abbr = studioAbbr(row.studio)

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="sheet-row-modal-title"
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "var(--color-backdrop)",
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
          width: "min(480px, 100%)",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--color-warn)",
                marginBottom: 6,
              }}
            >
              Overwrite confirm
            </div>
            <h2
              id="sheet-row-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 400,
                fontSize: 22,
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              Load this row?
            </h2>
          </div>
          <button
            type="button"
            onClick={onCancel}
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

        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.6, margin: 0 }}>
            Your manual inputs will be replaced. Director's note and destination are preserved.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <FieldBlock
              label="Current"
              lines={[
                currentFemale || currentMale
                  ? `${currentFemale || "—"}${currentMale ? ` / ${currentMale}` : ""}`
                  : "—",
              ]}
              muted
            />
            <FieldBlock
              label="After load"
              accent={color}
              lines={[
                row.female || row.male
                  ? `${row.female || "—"}${row.male ? ` / ${row.male}` : ""}`
                  : "—",
              ]}
            />
          </div>

          <div
            style={{
              padding: "10px 12px",
              background: "var(--color-elevated)",
              border: "1px solid var(--color-border)",
              fontSize: 11,
              color: "var(--color-text-muted)",
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span>
              <strong style={{ color: color, fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.1em" }}>{abbr}</strong>
            </span>
            {row.shoot_date && (
              <span>Shoot {row.shoot_date}</span>
            )}
            {row.tab_name && (
              <span style={{ color: "var(--color-text-faint)" }}>· {row.tab_name}</span>
            )}
          </div>
        </div>

        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            background: "var(--color-surface)",
          }}
        >
          <button
            type="button"
            onClick={onCancel}
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
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            autoFocus
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-warn)",
              color: "var(--color-base)",
              border: "1px solid var(--color-warn)",
              cursor: "pointer",
            }}
          >
            Overwrite & Load
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function FieldBlock({
  label,
  lines,
  accent,
  muted,
}: {
  label: string
  lines: string[]
  accent?: string
  muted?: boolean
}) {
  return (
    <div
      style={{
        padding: "10px 12px",
        background: "var(--color-elevated)",
        border: `1px solid ${accent ? `color-mix(in srgb, ${accent} 30%, transparent)` : "var(--color-border)"}`,
      }}
    >
      <div
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: accent ?? "var(--color-text-faint)",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      {lines.map((line, i) => (
        <div
          key={i}
          style={{
            fontSize: 12.5,
            color: muted ? "var(--color-text-muted)" : "var(--color-text)",
            fontWeight: muted ? 400 : 600,
          }}
        >
          {line}
        </div>
      ))}
    </div>
  )
}
