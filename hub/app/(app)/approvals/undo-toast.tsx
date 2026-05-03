"use client"

import { X } from "lucide-react"

// ─── Undo Toast ───────────────────────────────────────────────────────────────

export interface UndoToastProps {
  decision: "Approved" | "Rejected"
  count: number
  progress: number // 0–100
  onUndo: () => void
  onDismiss: () => void
}

export function UndoToast({ decision, count, progress, onUndo, onDismiss }: UndoToastProps) {
  const barColor = decision === "Approved" ? "var(--color-ok)" : "var(--color-err)"

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 500,
        background: "var(--color-elevated)",
        border: "1px solid var(--color-border)",
        borderRadius: 4,
        overflow: "hidden",
        minWidth: 200,
        boxShadow: "0 8px 24px rgba(0,0,0,.4)",
        animation: "toastSlideUp 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
      }}
    >
      {/* Countdown bar — scaleX avoids layout reflow on every tick */}
      <div
        aria-hidden="true"
        style={{
          height: 2,
          background: barColor,
          width: "100%",
          transform: `scaleX(${progress / 100})`,
          transformOrigin: "left",
          transition: "transform 60ms linear",
        }}
      />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "8px 12px",
        }}
      >
        <span style={{ fontSize: 12, color: "var(--color-text)", flex: 1 }}>
          {count > 1 ? `${decision} (${count})` : decision}
        </span>
        <button
          onClick={onUndo}
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-lime)",
            background: "none",
            border: "none",
            padding: "0 2px",
            cursor: "pointer",
            letterSpacing: "0.01em",
          }}
        >
          Undo
        </button>
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            display: "flex",
            alignItems: "center",
            color: "var(--color-text-muted)",
            background: "none",
            border: "none",
            padding: "0 2px",
            cursor: "pointer",
          }}
        >
          <X size={12} />
        </button>
      </div>
    </div>
  )
}
