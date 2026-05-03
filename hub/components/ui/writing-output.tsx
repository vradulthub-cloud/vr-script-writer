"use client"

import type { ReactNode } from "react"

/**
 * Hero header for the Writing Room output panel. Studio eyebrow + serif
 * title + optional secondary meta. Sits at the top of the writing-paper
 * surface so the talent name reads as a real article masthead, not a
 * generated-blob preview.
 *
 * Used by /scripts (talent names) and /descriptions (scene title).
 */
export function WritingHero({
  studioAbbr,
  studioColor,
  meta,
  title,
  byline,
}: {
  studioAbbr: string
  studioColor: string
  meta?: string | null
  title: string
  byline?: string | null
}) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: studioColor,
          }}
        >
          {studioAbbr}
        </span>
        {meta && (
          <>
            <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--color-paper-sub)" }} />
            <span
              style={{
                fontSize: 10,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--color-paper-sub)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {meta}
            </span>
          </>
        )}
      </div>
      <h1
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: "clamp(1.75rem, 1.4rem + 1.5vw, 2.25rem)",
          fontWeight: 600,
          color: "var(--color-paper-text)",
          lineHeight: 1.15,
          letterSpacing: "-0.01em",
          margin: 0,
        }}
      >
        {title}
      </h1>
      {byline && (
        <div
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 14,
            color: "var(--color-paper-sub)",
            marginTop: 6,
            fontStyle: "italic",
          }}
        >
          {byline}
        </div>
      )}
    </div>
  )
}

/**
 * Theme-as-blockquote — italic, indented, with a studio-colored left rule.
 * Used by /scripts when the parsed THEME section is available.
 */
export function ThemeBlockquote({
  text,
  studioColor,
}: {
  text: string
  studioColor: string
}) {
  return (
    <blockquote
      style={{
        fontFamily: "var(--font-serif)",
        fontSize: 18,
        fontStyle: "italic",
        color: "var(--color-paper-sub)",
        borderLeft: `3px solid ${studioColor}`,
        paddingLeft: 22,
        lineHeight: 1.65,
        margin: "0 0 24px",
      }}
    >
      {text}
    </blockquote>
  )
}

/**
 * Plot prose — paragraphs in serif body face. The cinematic plot read.
 */
export function PlotProse({ text }: { text: string }) {
  const paragraphs = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean)
  return (
    <div style={{ marginBottom: 24 }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 800,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--color-paper-sub)",
          marginBottom: 12,
          fontFamily: "var(--font-sans)",
        }}
      >
        Plot
      </div>
      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 16,
          lineHeight: 1.85,
          color: "var(--color-paper-text)",
        }}
      >
        {paragraphs.map((p, i) => (
          <p key={i} style={{ marginBottom: "1.2em" }}>
            {p}
          </p>
        ))}
      </div>
    </div>
  )
}

/**
 * 3-column metadata strip — Location / Her Wardrobe / His Wardrobe.
 * Drops empty cells so a Solo scene with no male wardrobe still looks tidy.
 */
export function MetaStrip({
  rows,
}: {
  rows: { label: string; value: string }[]
}) {
  const populated = rows.filter(r => r.value && r.value.trim() !== "")
  if (populated.length === 0) return null
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${Math.min(populated.length, 3)}, 1fr)`,
        gap: 1,
        background: "var(--color-paper-rule)",
        border: "1px solid var(--color-paper-rule)",
        marginBottom: 24,
      }}
    >
      {populated.map(({ label, value }) => (
        <div
          key={label}
          style={{ padding: "14px 16px", background: "var(--color-paper)" }}
        >
          <div
            style={{
              fontSize: 8,
              fontWeight: 800,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--color-paper-sub)",
              marginBottom: 6,
              fontFamily: "var(--font-sans)",
            }}
          >
            {label}
          </div>
          <div
            style={{
              fontSize: 13,
              color: "var(--color-paper-text)",
              lineHeight: 1.5,
              fontFamily: "var(--font-sans)",
            }}
          >
            {value}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Validation passed strip — green-tinted "✓ Validation passed".
 * Shown after a successful generate finishes streaming.
 */
export function ValidationStrip({
  ok = true,
  text = "Validation passed",
  detail,
}: {
  ok?: boolean
  text?: string
  detail?: ReactNode
}) {
  const accent = ok ? "var(--color-ok)" : "var(--color-warn)"
  return (
    <div
      style={{
        padding: "10px 14px",
        background: `color-mix(in srgb, ${accent} 10%, transparent)`,
        border: `1px solid color-mix(in srgb, ${accent} 25%, transparent)`,
        borderRadius: 8,
        marginBottom: 16,
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontFamily: "var(--font-sans)",
      }}
    >
      <span style={{ fontSize: 13, color: accent, fontWeight: 700 }}>
        {ok ? "✓" : "!"}
      </span>
      <span style={{ fontSize: 12, color: accent, fontWeight: 600 }}>
        {text}
      </span>
      {detail && (
        <span style={{ fontSize: 11, color: "var(--color-paper-sub)" }}>{detail}</span>
      )}
    </div>
  )
}
