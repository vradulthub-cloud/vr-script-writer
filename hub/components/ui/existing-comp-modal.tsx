"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import type { ExistingComp } from "@/lib/api"

/** Detail modal for a single existing compilation row. Lifts the scene grid
 *  + description + metadata out of the inline accordion so the Existing
 *  table stays a clean list, and the detail view has room to breathe. */
export function ExistingCompModal({
  comp,
  studioColor,
  onClose,
}: {
  comp: ExistingComp
  studioColor: string
  onClose: () => void
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

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

  if (!mounted) return null

  const stat = statusColors(comp.status)

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="comp-modal-title"
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
          width: "min(720px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
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
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: studioColor,
                marginBottom: 6,
              }}
            >
              {comp.comp_id}{comp.volume ? ` · ${comp.volume}` : ""}
            </div>
            <h2
              id="comp-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 800,
                fontSize: 28,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              {comp.title || <span style={{ color: "var(--color-text-faint)" }}>Untitled</span>}
            </h2>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  padding: "3px 8px",
                  color: stat.fg,
                  background: stat.bg,
                  border: `1px solid ${stat.border}`,
                }}
              >
                {comp.status || "Draft"}
              </span>
              <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                {comp.scene_count} scene{comp.scene_count === 1 ? "" : "s"}
              </span>
              {comp.created && (
                <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                  Created {comp.created}
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
          {comp.description && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <SectionLabel>Description</SectionLabel>
              <p style={{ fontSize: 12.5, color: "var(--color-text)", lineHeight: 1.65, whiteSpace: "pre-wrap", margin: 0 }}>
                {comp.description}
              </p>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <SectionLabel>Scenes</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {comp.scenes.map((sc) => (
                <div
                  key={`${comp.comp_id}-${sc.scene_num}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "28px auto 1fr auto auto",
                    alignItems: "center",
                    columnGap: 12,
                    padding: "8px 12px",
                    background: "var(--color-elevated)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--color-text-faint)",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {String(sc.scene_num).padStart(2, "0")}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      letterSpacing: "0.08em",
                      fontWeight: 700,
                      color: studioColor,
                    }}
                  >
                    {sc.scene_id}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--color-text)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {sc.title || <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                    {sc.performers || "—"}
                  </span>
                  {sc.mega_link ? (
                    <a
                      href={sc.mega_link}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: "0.1em",
                        textTransform: "uppercase",
                        color: studioColor,
                        textDecoration: "none",
                        padding: "2px 8px",
                        border: `1px solid color-mix(in srgb, ${studioColor} 35%, transparent)`,
                      }}
                    >
                      MEGA →
                    </a>
                  ) : (
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: "0.1em",
                        textTransform: "uppercase",
                        color: "var(--color-text-faint)",
                        padding: "2px 8px",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      Pending
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
            background: "var(--color-surface)",
          }}
        >
          <span style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            {comp.created_by ? `By ${comp.created_by}` : "—"}
            {comp.updated && comp.updated !== comp.created && ` · Updated ${comp.updated}`}
          </span>
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
        </div>
      </div>
    </div>,
    document.body,
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

function statusColors(status: string) {
  const s = status.trim().toLowerCase()
  if (s === "published") return { fg: "var(--color-ok)", bg: "color-mix(in srgb, var(--color-ok) 12%, transparent)", border: "color-mix(in srgb, var(--color-ok) 30%, transparent)" }
  if (s === "planned")   return { fg: "var(--color-text)", bg: "var(--color-elevated)", border: "var(--color-border)" }
  return { fg: "var(--color-text-muted)", bg: "color-mix(in srgb, var(--color-text-muted) 10%, transparent)", border: "var(--color-border)" }
}
