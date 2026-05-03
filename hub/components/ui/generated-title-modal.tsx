"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X, Wand2, Check, RotateCcw } from "lucide-react"
import type { Scene } from "@/lib/api"
import { studioColor, studioAbbr } from "@/lib/studio-colors"

/** Focused preview for an AI-generated scene title. Shows the draft in
 *  context (scene metadata + plot snippet) and gives the user room to
 *  Apply, Regenerate, or Discard — replacing the cramped inline pill when
 *  the user wants a closer look. */
export function GeneratedTitleModal({
  scene,
  title,
  busy,
  error,
  onApply,
  onRegenerate,
  onDiscard,
  onClose,
}: {
  scene: Scene
  title: string
  busy: "idle" | "loading" | "saving"
  error: string | null
  onApply: () => void
  onRegenerate: () => void
  onDiscard: () => void
  onClose: () => void
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      if (busy === "idle") onClose()
    }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose, busy])

  if (!mounted) return null

  const color = studioColor(scene.studio)
  const abbr = studioAbbr(scene.studio)
  const plotSnippet = (scene.plot || scene.theme || "").trim()

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="gentitle-modal-title"
      onClick={busy === "idle" ? onClose : undefined}
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
          width: "min(520px, 100%)",
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
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color,
                marginBottom: 6,
              }}
            >
              {abbr} · {scene.id} · Title draft
            </div>
            <h2
              id="gentitle-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 400,
                fontSize: 22,
                lineHeight: 1.15,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
                wordBreak: "break-word",
              }}
            >
              {title || <span style={{ color: "var(--color-text-faint)" }}>Generating…</span>}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy !== "idle"}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: busy !== "idle" ? "wait" : "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              opacity: busy !== "idle" ? 0.5 : 1,
            }}
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
          {(scene.performers || scene.release_date) && (
            <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 12, rowGap: 4, fontSize: 11 }}>
              {scene.performers && (
                <>
                  <span style={labelStyle}>Performers</span>
                  <span style={{ color: "var(--color-text)", fontSize: 12 }}>{scene.performers}</span>
                </>
              )}
              {scene.release_date && (
                <>
                  <span style={labelStyle}>Release</span>
                  <span style={{ color: "var(--color-text)", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                    {scene.release_date.slice(0, 10)}
                  </span>
                </>
              )}
            </div>
          )}

          {plotSnippet && (
            <div>
              <div style={{ ...labelStyle, marginBottom: 6 }}>Source plot</div>
              <p
                style={{
                  margin: 0,
                  fontSize: 12.5,
                  lineHeight: 1.55,
                  color: "var(--color-text-muted)",
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border)",
                  padding: "10px 12px",
                  maxHeight: 140,
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                }}
              >
                {plotSnippet}
              </p>
            </div>
          )}

          {error && (
            <p style={{ margin: 0, fontSize: 11, color: "var(--color-err)" }}>{error}</p>
          )}
        </div>

        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "space-between",
            gap: 8,
            background: "var(--color-surface)",
          }}
        >
          <button
            type="button"
            onClick={onDiscard}
            disabled={busy !== "idle"}
            style={{
              padding: "6px 12px",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: busy !== "idle" ? "wait" : "pointer",
              opacity: busy !== "idle" ? 0.5 : 1,
            }}
          >
            Discard
          </button>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={onRegenerate}
              disabled={busy !== "idle"}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                background: "transparent",
                color: busy === "loading" ? "var(--color-text-faint)" : color,
                border: `1px solid color-mix(in srgb, ${color} 32%, transparent)`,
                cursor: busy !== "idle" ? "wait" : "pointer",
              }}
            >
              {busy === "loading" ? <RotateCcw size={11} /> : <Wand2 size={11} />}
              {busy === "loading" ? "Generating…" : "Regenerate"}
            </button>
            <button
              type="button"
              onClick={onApply}
              disabled={busy !== "idle" || !title}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                fontSize: 10,
                fontWeight: 800,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                background: "var(--color-lime)",
                color: "var(--color-lime-ink)",
                border: "1px solid var(--color-lime)",
                cursor: busy === "saving" ? "wait" : "pointer",
                opacity: busy !== "idle" || !title ? 0.5 : 1,
              }}
            >
              <Check size={11} />
              {busy === "saving" ? "Saving…" : "Apply title"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

const labelStyle: React.CSSProperties = {
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: "0.16em",
  textTransform: "uppercase",
  color: "var(--color-text-faint)",
  alignSelf: "center",
}
