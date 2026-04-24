"use client"

import { useEffect, useState } from "react"
import { HelpCircle, X } from "lucide-react"

/**
 * Hub help surface. Fills the critique's "help/docs = 1/4" gap with a
 * minimal, permanent cheat sheet reachable from the topbar. Three sections:
 *   — Keyboard shortcuts
 *   — Glossary (the three domain terms newcomers routinely ask about)
 *   — What "Today" picks (the dashboard's briefing logic explained)
 *
 * Deliberately low-chrome: modal, no tabs, no search. If the content grows
 * past one screen we'll add sections; for now the whole thing should fit.
 */
export function HelpButton() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  // Global "?" shortcut to open (but not inside inputs).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "?") return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return
      e.preventDefault()
      setOpen(v => !v)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Help (?)"
        aria-label="Open help"
        className="hidden sm:inline-flex items-center justify-center rounded transition-colors hover:bg-[--color-elevated]"
        style={{
          padding: 5,
          border: "1px solid var(--color-border)",
          background: "transparent",
          color: "var(--color-text-faint)",
          cursor: "pointer",
        }}
      >
        <HelpCircle size={13} aria-hidden="true" />
      </button>

      {open && <HelpModal onClose={() => setOpen(false)} />}
    </>
  )
}

function HelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Help"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "color-mix(in srgb, var(--color-base) 78%, transparent)",
        backdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "10vh",
        zIndex: 200,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          width: "min(640px, calc(100vw - 32px))",
          maxHeight: "78vh",
          overflow: "auto",
          boxShadow: "0 24px 64px rgba(0,0,0,0.4)",
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 18px",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <h2
            style={{
              margin: 0,
              fontFamily: "var(--font-display)",
              fontSize: "var(--text-title)",
              fontWeight: 600,
              letterSpacing: "-0.01em",
              color: "var(--color-text)",
              lineHeight: 1.2,
            }}
          >
            Quick reference
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close help"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 22 }}>
          <Section title="Keyboard">
            <Shortcut keys={["⌘", "K"]} desc="Jump to… (command palette)" />
            <Shortcut keys={["?"]} desc="Open this help surface" />
            <Shortcut keys={["Esc"]} desc="Close any open modal or palette" />
            <Shortcut keys={["Tab"]} desc="Step through interactive elements. Focus ring is lime." />
            <Shortcut keys={["j", "k"]} desc="Step rows up/down in the dashboard's Recent activity feed (aliases for ↑/↓)." />
            <Shortcut keys={["Enter"]} desc="Open the focused row." />
          </Section>

          <Section title="Glossary">
            <Term
              label="Grail Assets"
              def="The master catalog of scenes that are live or in-flight across every studio. The /missing route highlights ones still lacking a description, videos, thumbnail, photos, or storyboard."
            />
            <Term
              label="Triage"
              def="The act of working through scenes that are short on assets, starting with whichever releases soonest. The dashboard's Today briefing and /missing's Next up briefing both pick a starting point for you."
            />
            <Term
              label="Aging shoot"
              def="A shoot that wrapped more than 72 hours ago but still has asset gaps. Aging shoots are the most urgent category the Today briefing surfaces, because every hour past wrap makes the production more likely to ship late."
            />
          </Section>

          <Section title="How Today is picked">
            <p style={pStyle}>
              The dashboard's Today briefing picks one pending item from this priority stack and surfaces it as a focal action:
            </p>
            <ol style={{ ...pStyle, paddingLeft: 18, margin: 0 }}>
              <li>Aging shoots (3+ days past wrap, still incomplete)</li>
              <li>Catalog-wide missing assets ≥ 10 scenes</li>
              <li>Scripts queued for writing</li>
              <li>"All clear" if none of the above</li>
            </ol>
            <p style={pStyle}>
              Tone of the big numeral ramps with magnitude: amber for 1–5, red-orange for 6–20, full red for 21+. The "!" state means Today couldn&rsquo;t be computed — the production server is unreachable.
            </p>
          </Section>
        </div>
      </div>
    </div>
  )
}

const pStyle = {
  margin: 0,
  fontSize: 12.5,
  lineHeight: 1.55,
  color: "var(--color-text-muted)",
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <h3
        style={{
          margin: 0,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--color-text-faint)",
        }}
      >
        {title}
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>{children}</div>
    </section>
  )
}

function Shortcut({ keys, desc }: { keys: string[]; desc: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ display: "flex", gap: 4, minWidth: 88 }}>
        {keys.map(k => (
          <kbd
            key={k}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              padding: "2px 6px",
              background: "var(--color-elevated)",
              color: "var(--color-text)",
              border: "1px solid var(--color-border)",
              borderRadius: 3,
              lineHeight: 1.3,
              minWidth: 22,
              textAlign: "center",
            }}
          >
            {k}
          </kbd>
        ))}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--color-text)", lineHeight: 1.45 }}>{desc}</div>
    </div>
  )
}

function Term({ label, def }: { label: string; def: string }) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--color-text-muted)", lineHeight: 1.55 }}>
        {def}
      </div>
    </div>
  )
}
