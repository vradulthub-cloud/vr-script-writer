"use client"

import type { ReactNode } from "react"
import { useEffect, useState } from "react"
import { studioColor } from "@/lib/studio-colors"

/**
 * The hub's sole page-title primitive. Every top-level route renders one of
 * these. Carries the Cabinet Grotesk display face + a bottom rule; optional
 * studio accent tints the eyebrow and adds a 2px left rule that frames the
 * title block — "studio color owns its context" per the brand brief.
 *
 * Deliberately unopinionated about the actions slot: pass in filter tabs,
 * buttons, a search input, whatever the page needs on the right.
 *
 * Responsive behavior: at narrow viewports (<900px) the actions slot
 * collapses onto its own row beneath the title to avoid z-stacking with
 * long filter-tab rows and the eyebrow. TKT-0098.
 */
export function PageHeader({
  title,
  eyebrow,
  subtitle,
  actions,
  studioAccent,
  compact = false,
}: {
  title: ReactNode
  eyebrow?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  studioAccent?: string
  /**
   * Compact mode: demotes the h1 to a ~20px display-face line and drops the
   * bottom rule. Use when the page's real focal element (e.g. TodayBriefing
   * on the dashboard) lives immediately below and deserves to be the hero.
   */
  compact?: boolean
}) {
  const accent = studioAccent ? studioColor(studioAccent) : undefined
  const stacked = useStackedLayout()

  // Column template: accent rule column only when we have a studio accent
  // AND we're in side-by-side layout. When stacked, the title and actions
  // live in one full-width column so long filter bars don't squish the h1.
  const columns = stacked
    ? (accent ? "2px minmax(0, 1fr)" : "minmax(0, 1fr)")
    : (accent ? "2px minmax(0, 1fr) auto" : "minmax(0, 1fr) auto")

  return (
    <header
      className="page-header"
      style={{
        display: "grid",
        gridTemplateColumns: columns,
        alignItems: "end",
        gap: 16,
        columnGap: accent ? 14 : 16,
        marginBottom: compact ? 16 : 24,
        paddingBottom: compact ? 0 : 20,
        borderBottom: compact ? "none" : "1px solid var(--color-border)",
      }}
    >
      {accent && (
        <span
          aria-hidden="true"
          style={{
            alignSelf: "stretch",
            background: accent,
            borderRadius: 1,
            width: 2,
          }}
        />
      )}

      <div style={{ minWidth: 0 }}>
        {/* Compact mode pulls the eyebrow inline with the title on a single
            row, separated by a thin rule. Reclaims ~30px of vertical space
            on routes where the real focal element lives below the header
            (e.g. the dashboard's TodayBriefing). */}
        {compact && eyebrow ? (
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: accent ?? "var(--color-text-faint)",
                whiteSpace: "nowrap",
              }}
            >
              {eyebrow}
            </span>
            <span
              aria-hidden="true"
              style={{
                width: 1,
                height: 12,
                background: "var(--color-border)",
                alignSelf: "center",
              }}
            />
            <h1
              className="display-hero"
              style={{ fontSize: "1.375rem", lineHeight: 1.1, letterSpacing: "-0.015em" }}
            >
              {title}
            </h1>
          </div>
        ) : (
          <>
            {eyebrow && (
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: accent ?? "var(--color-text-faint)",
                  marginBottom: 10,
                }}
              >
                {eyebrow}
              </div>
            )}

            <h1 className="display-hero">{title}</h1>
          </>
        )}

        {subtitle && (
          <div
            style={{
              fontSize: 13,
              color: "var(--color-text-muted)",
              marginTop: 8,
              maxWidth: "65ch",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>

      {actions && (
        <div
          style={{
            gridColumn: stacked ? (accent ? "2" : "1") : undefined,
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            justifyContent: stacked ? "flex-start" : "flex-end",
            marginTop: stacked ? 12 : 0,
          }}
        >
          {actions}
        </div>
      )}
    </header>
  )
}

/**
 * Stacks actions below title when viewport is narrow enough that side-by-side
 * layout causes wrapping collisions. Threshold 900px: above → side-by-side;
 * below → stacked. Uses matchMedia for performance; hydration-safe via a
 * state initializer that matches SSR default (side-by-side) and syncs after
 * mount.
 */
function useStackedLayout() {
  const [stacked, setStacked] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    const mq = window.matchMedia("(max-width: 900px)")
    const sync = () => setStacked(mq.matches)
    sync()
    mq.addEventListener("change", sync)
    return () => mq.removeEventListener("change", sync)
  }, [])
  return stacked
}
