import Link from "next/link"

export type BriefingTone = "urgent" | "attention" | "calm" | "error"

export interface Briefing {
  tone: BriefingTone
  count: number
  /** Label above the numeral. Default "Today". Use "Next up" or "Priority" on non-dashboard pages so the word stays specific. */
  eyebrow?: string
  /** Main line to the right of the numeral. For count > 0, the numeral is prepended separately — so headline should not start with the count. */
  headline: string
  detail: string
  cta: { href: string; label: string } | null
  secondary: string[]
}

/**
 * Focal-action briefing. Lives at the top of a page (under the PageHeader),
 * collapses 5+ surfaces of information into one actionable sentence with
 * one primary CTA. The dashboard uses it for "what's urgent today"; /missing
 * and /scripts use page-specific variants.
 *
 * Tone-ramps the numeral colour by magnitude (tone field) so a single aging
 * item doesn't wear the same red as 50. Calm state hides the numeral and
 * shows a "✓".
 *
 * Numeral size ramps with digit count so 3-digit values don't blow past the
 * headline column.
 */
export function TodayBriefing({ briefing }: { briefing: Briefing }) {
  const accentColor = toneToAccent(briefing.tone)
  const numeralSize = toneSize(briefing.count)
  const eyebrow = briefing.eyebrow ?? "Today"

  return (
    <section
      aria-label={eyebrow}
      className="today-briefing"
      style={{
        marginBottom: 28,
        display: "grid",
        gridTemplateColumns: "auto minmax(0, 1fr) auto",
        alignItems: "center",
        gap: 20,
        paddingBottom: 20,
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--color-text-faint)",
          }}
        >
          {eyebrow}
        </div>
        <div
          style={{
            fontFamily: "var(--font-display-hero)",
            fontWeight: 400,
            fontSize: numeralSize,
            lineHeight: 0.95,
            letterSpacing: "-0.02em",
            color: briefing.count > 0 || briefing.tone === "error" ? accentColor : "var(--color-text)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {briefing.tone === "error" ? "!" : briefing.count > 0 ? briefing.count.toLocaleString() : "✓"}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
        <div
          style={{
            fontSize: "var(--text-title)",
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: "var(--color-text)",
            lineHeight: 1.25,
          }}
        >
          {briefing.headline}
        </div>
        <div
          style={{
            fontSize: 13,
            color: "var(--color-text-muted)",
            maxWidth: "65ch",
            lineHeight: 1.45,
          }}
        >
          {briefing.detail}
        </div>
        {briefing.secondary.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
              marginTop: 2,
              fontSize: 11,
              color: "var(--color-text-faint)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {briefing.secondary.map((s, i) => (
              <span key={i}>
                {i > 0 && <span style={{ marginRight: 6, opacity: 0.5 }}>·</span>}
                {s}
              </span>
            ))}
          </div>
        )}
      </div>

      {briefing.cta && (
        <Link
          href={briefing.cta.href}
          prefetch={false}
          style={{
            background: "var(--color-lime)",
            color: "var(--color-lime-ink)",
            padding: "10px 18px",
            borderRadius: 4,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: "0.02em",
            textDecoration: "none",
            whiteSpace: "nowrap",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {briefing.cta.label} <span aria-hidden="true">→</span>
        </Link>
      )}
    </section>
  )
}

// ─── Tone ramps ──────────────────────────────────────────────────────────────

function toneToAccent(tone: BriefingTone): string {
  switch (tone) {
    case "urgent":    return "var(--color-err)"
    case "attention": return "var(--color-warn)"
    case "error":     return "var(--color-text-faint)"
    case "calm":
    default:          return "var(--color-text-muted)"
  }
}

/**
 * Scale the numeral by magnitude — 1-digit vs 3-digit need different sizes so
 * neither loses weight nor crushes the headline column.
 */
function toneSize(count: number): number {
  if (count <= 0)   return 44  // ✓ / !
  if (count < 10)   return 64
  if (count < 100)  return 56
  return 48
}

/**
 * Build the tone for a *count-of-pending-items* briefing.
 *
 * A single item used to wear amber ("attention") — the same colour we show
 * when five things are on fire. That miscalibrated the ramp: every Monday
 * morning with one stuck shoot looked as alarming as a real backlog, and
 * users tuned the signal out. The thresholds below keep count=1 on neutral
 * so the numeral still reads but without crying wolf.
 *
 *   0      → calm       (shows ✓)
 *   1      → calm       (shows "1" in muted neutral — informational)
 *   2 – 5  → attention  (amber — worth a look, not yet urgent)
 *   6 +    → urgent     (red — backlog; interrupt the day)
 */
export function toneForCount(count: number): BriefingTone {
  if (count <= 1) return "calm"
  if (count < 6)  return "attention"
  return "urgent"
}
