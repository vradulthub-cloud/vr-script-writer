"use client"

import { useEffect, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"

/** Generic confirmation dialog — replaces window.confirm for destructive or
 *  non-obvious actions. Two-button footer (cancel + confirm); the confirm
 *  button can be tinted by tone ("danger" → var(--color-err)). */
export function ConfirmModal({
  title,
  eyebrow,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "neutral",
  onConfirm,
  onCancel,
  busy = false,
}: {
  title: string
  eyebrow?: string
  children: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: "neutral" | "danger" | "warn"
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel()
    }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onCancel, busy])

  if (!mounted) return null

  const confirmColor = tone === "danger"
    ? "var(--color-err)"
    : tone === "warn"
      ? "var(--color-warn)"
      : "var(--color-lime)"
  const confirmInk = tone === "neutral" ? "var(--color-lime-ink)" : "var(--color-base)"
  const eyebrowColor = tone === "danger"
    ? "var(--color-err)"
    : tone === "warn"
      ? "var(--color-warn)"
      : "var(--color-text-faint)"

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
      onClick={busy ? undefined : onCancel}
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
          width: "min(460px, 100%)",
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
            {eyebrow && (
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: eyebrowColor,
                  marginBottom: 6,
                }}
              >
                {eyebrow}
              </div>
            )}
            <h2
              id="confirm-modal-title"
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
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: busy ? "wait" : "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              opacity: busy ? 0.5 : 1,
            }}
          >
            <X size={14} />
          </button>
        </div>

        <div
          style={{
            padding: "18px 24px",
            fontSize: 13,
            lineHeight: 1.6,
            color: "var(--color-text)",
          }}
        >
          {children}
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
            disabled={busy}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: busy ? "wait" : "pointer",
              opacity: busy ? 0.5 : 1,
            }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            autoFocus
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: confirmColor,
              color: confirmInk,
              border: `1px solid ${confirmColor}`,
              cursor: busy ? "wait" : "pointer",
              opacity: busy ? 0.5 : 1,
            }}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
