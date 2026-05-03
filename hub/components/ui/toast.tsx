"use client"

import { useEffect, useState, useCallback } from "react"
import { X } from "lucide-react"

type Variant = "error" | "info" | "success"

interface ToastAction {
  label: string
  /** Click handler. Toast is dismissed automatically after the handler runs. */
  onClick: () => void
}

interface Toast {
  id: number
  msg: string
  variant: Variant
  action?: ToastAction
}

interface ToastDetail {
  msg: string
  variant?: Variant
  action?: ToastAction
}

const AUTO_DISMISS_MS = 5000
const UNDO_DISMISS_MS = 8000   // actionable toasts linger longer so the user has time to click

/** Dispatch a toast from anywhere. No React required. */
export function showToast(
  msg: string,
  variantOrOptions: Variant | { variant?: Variant; action?: ToastAction } = "info",
) {
  if (typeof window === "undefined") return
  const detail: ToastDetail =
    typeof variantOrOptions === "string"
      ? { msg, variant: variantOrOptions }
      : { msg, variant: variantOrOptions.variant, action: variantOrOptions.action }
  window.dispatchEvent(new CustomEvent<ToastDetail>("hub:toast", { detail }))
}

/**
 * Show a "did the thing — [Undo]" toast. Standard pattern for destructive or
 * reversible writes: optimistic update → API call → on success, showUndoToast
 * → if the user clicks Undo, call the compensating API. The toast lingers
 * 8s (vs 5s for plain info) because clicking Undo takes deliberate action.
 */
export function showUndoToast(msg: string, onUndo: () => void) {
  showToast(msg, { variant: "success", action: { label: "Undo", onClick: onUndo } })
}

/** Mount once at the app shell root. Listens for hub:toast events. */
export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const remove = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    let counter = 0
    function onToast(e: Event) {
      const detail = (e as CustomEvent<ToastDetail>).detail
      if (!detail?.msg) return
      const id = ++counter
      setToasts(prev => [...prev, { id, msg: detail.msg, variant: detail.variant ?? "info", action: detail.action }])
      const dismissMs = detail.action ? UNDO_DISMISS_MS : AUTO_DISMISS_MS
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, dismissMs)
    }
    window.addEventListener("hub:toast", onToast)
    return () => window.removeEventListener("hub:toast", onToast)
  }, [])

  if (toasts.length === 0) return null

  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 500,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "none",
      }}
    >
      {toasts.map(t => {
        const barColor =
          t.variant === "error"   ? "var(--color-err)" :
          t.variant === "success" ? "var(--color-ok)"  :
                                    "var(--color-text-muted)"
        return (
          <div
            key={t.id}
            role="status"
            aria-live="polite"
            style={{
              pointerEvents: "auto",
              background: "var(--color-elevated)",
              border: "1px solid var(--color-border)",
              borderRadius: 4,
              overflow: "hidden",
              minWidth: 240,
              maxWidth: 360,
              boxShadow: "0 8px 24px rgba(0,0,0,.4)",
              animation: "toastSlideUp 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
            }}
          >
            <div aria-hidden="true" style={{ height: 2, background: barColor, width: "100%" }} />
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 12px" }}>
              <span style={{ fontSize: 12, color: "var(--color-text)", flex: 1, lineHeight: 1.4 }}>
                {t.msg}
              </span>
              {t.action && (
                <button
                  onClick={() => { t.action?.onClick(); remove(t.id) }}
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    color: "var(--color-lime)",
                    background: "transparent",
                    border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                    padding: "3px 10px",
                    borderRadius: 3,
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  {t.action.label}
                </button>
              )}
              <button
                onClick={() => remove(t.id)}
                aria-label="Dismiss"
                style={{
                  display: "flex",
                  alignItems: "center",
                  color: "var(--color-text-muted)",
                  background: "none",
                  border: "none",
                  padding: "0 2px",
                  cursor: "pointer",
                  flexShrink: 0,
                }}
              >
                <X size={12} />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
