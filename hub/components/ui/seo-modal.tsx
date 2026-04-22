"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X, Wand2 } from "lucide-react"

/** Modal that lifts the SEO meta-title/description editor out of the inline
 *  description output. The inline strip got cramped once the output grew,
 *  and character counts are easier to eyeball in a focused view. */
export function SeoModal({
  metaTitle,
  metaDesc,
  studioColor,
  loading,
  error,
  onChangeTitle,
  onChangeDesc,
  onGenerate,
  onClose,
}: {
  metaTitle: string
  metaDesc: string
  studioColor: string
  loading: boolean
  error: string | null
  onChangeTitle: (v: string) => void
  onChangeDesc: (v: string) => void
  onGenerate: () => void
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

  const titleOverBudget = metaTitle.length > 60
  const descOverBudget = metaDesc.length > 155

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="seo-modal-title"
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
          width: "min(560px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
          minHeight: 0,
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
            flexShrink: 0,
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
                color: studioColor,
                marginBottom: 6,
              }}
            >
              SEO · Meta Tags
            </div>
            <h2
              id="seo-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 800,
                fontSize: 24,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              Search listing
            </h2>
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

        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 16, overflowY: "auto", flex: "1 1 auto", minHeight: 0 }}>
          <button
            type="button"
            onClick={onGenerate}
            disabled={loading}
            style={{
              alignSelf: "flex-start",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              background: `color-mix(in srgb, ${studioColor} 12%, transparent)`,
              color: loading ? "var(--color-text-faint)" : studioColor,
              border: `1px solid color-mix(in srgb, ${studioColor} 32%, transparent)`,
              cursor: loading ? "wait" : "pointer",
            }}
          >
            <Wand2 size={11} />
            {loading ? "Generating…" : "Generate from description"}
          </button>

          {error && (
            <p style={{ fontSize: 11, color: "var(--color-err)", margin: 0 }}>{error}</p>
          )}

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
              <label htmlFor="seo-meta-title" style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)" }}>
                Meta Title
              </label>
              <span style={{ fontSize: 10, color: titleOverBudget ? "var(--color-warn)" : "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
                {metaTitle.length}/60
              </span>
            </div>
            <input
              id="seo-meta-title"
              type="text"
              value={metaTitle}
              onChange={e => onChangeTitle(e.target.value.slice(0, 60))}
              maxLength={60}
              placeholder="Click Generate to draft a title…"
              style={{
                width: "100%",
                padding: "8px 10px",
                fontSize: 13,
                fontWeight: 500,
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
                outline: "none",
              }}
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
              <label htmlFor="seo-meta-desc" style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)" }}>
                Meta Description
              </label>
              <span style={{ fontSize: 10, color: descOverBudget ? "var(--color-warn)" : "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
                {metaDesc.length}/155
              </span>
            </div>
            <textarea
              id="seo-meta-desc"
              value={metaDesc}
              onChange={e => onChangeDesc(e.target.value.slice(0, 155))}
              rows={3}
              maxLength={155}
              placeholder="Click Generate to draft a description…"
              style={{
                width: "100%",
                padding: "8px 10px",
                fontSize: 12,
                lineHeight: 1.55,
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
                resize: "none",
                outline: "none",
              }}
            />
          </div>

          {/* SERP preview — sanity-check the title + desc as a search result */}
          {(metaTitle || metaDesc) && (
            <div>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 6 }}>
                Preview
              </div>
              <div
                style={{
                  padding: "10px 12px",
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ fontSize: 15, color: "#8ab4f8", lineHeight: 1.3, marginBottom: 2, fontWeight: 500 }}>
                  {metaTitle || <span style={{ color: "var(--color-text-faint)" }}>Title preview…</span>}
                </div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.5 }}>
                  {metaDesc || <span style={{ color: "var(--color-text-faint)" }}>Description preview…</span>}
                </div>
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            flexShrink: 0,
            background: "var(--color-surface)",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-lime)",
              color: "var(--color-lime-ink)",
              border: "1px solid var(--color-lime)",
              cursor: "pointer",
            }}
          >
            Done
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
