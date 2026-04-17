"use client"

import { useEffect, useState, useCallback } from "react"
import { X } from "lucide-react"

type Variant = "error" | "info" | "success"

interface Toast {
  id: number
  msg: string
  variant: Variant
}

interface ToastDetail {
  msg: string
  variant?: Variant
}

const AUTO_DISMISS_MS = 5000

/** Dispatch a toast from anywhere. No React required. */
export function showToast(msg: string, variant: Variant = "info") {
  if (typeof window === "undefined") return
  window.dispatchEvent(new CustomEvent<ToastDetail>("hub:toast", { detail: { msg, variant } }))
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
      setToasts(prev => [...prev, { id, msg: detail.msg, variant: detail.variant ?? "info" }])
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, AUTO_DISMISS_MS)
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
