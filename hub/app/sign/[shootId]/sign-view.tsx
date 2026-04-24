"use client"

import { useState, useEffect } from "react"
import { CheckCircle2 } from "lucide-react"

const STUDIO_COLOR: Record<string, string> = {
  FuckPassVR: "#f97316",
  VRHush:     "#8b5cf6",
  VRAllure:   "#ec4899",
  NaughtyJOI: "#3b82f6",
}

interface Props {
  shootId: string
  talent: string    // slug, e.g. "SofiaRed"
  display: string   // pretty name, e.g. "Sofia Red"
  studio: string    // e.g. "VRHush"
}

export function SignView({ shootId, talent, display, studio }: Props) {
  const [confirmed, setConfirmed] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const accent = STUDIO_COLOR[studio] ?? "var(--color-lime)"

  // Track when the iframe has likely been scrolled (proxy: time on page ≥ 5s)
  useEffect(() => {
    const t = setTimeout(() => setScrolled(true), 5000)
    return () => clearTimeout(t)
  }, [])

  function handleConfirm() {
    setConfirmed(true)
    // Notify the opener tab so it can auto-advance
    try {
      window.opener?.postMessage(`compliance:signed:${talent}`, window.location.origin)
    } catch {
      // cross-origin or no opener — no-op
    }
  }

  const pdfUrl = `/api/compliance/${encodeURIComponent(shootId)}/pdf?talent=${encodeURIComponent(talent)}`

  if (confirmed) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        background: "var(--color-base)", gap: 20, padding: 32,
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: "50%",
          background: "rgba(190,214,47,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <CheckCircle2 size={36} color="var(--color-lime)" />
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text)", marginBottom: 8 }}>
            Agreement confirmed
          </div>
          <div style={{ fontSize: 15, color: "var(--color-text-faint)", lineHeight: 1.5 }}>
            Thank you, {display}. Your signature has been recorded.
            <br />You may close this tab.
          </div>
        </div>
        <button
          onClick={() => window.close()}
          style={{
            marginTop: 8,
            background: "var(--color-lime)", border: "none", borderRadius: 10,
            padding: "14px 28px", fontSize: 15, fontWeight: 700,
            color: "#000", cursor: "pointer",
          }}
        >
          Close
        </button>
      </div>
    )
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100dvh",
      background: "var(--color-base)", overflow: "hidden",
    }}>

      {/* Header */}
      <div style={{
        flexShrink: 0,
        background: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        padding: "14px 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 2 }}>
            Compliance Review
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)" }}>
            {display}
            {studio && (
              <span style={{ fontSize: 12, fontWeight: 600, color: accent, marginLeft: 10 }}>
                {studio}
              </span>
            )}
          </div>
        </div>
        <div style={{
          fontSize: 11, color: "var(--color-text-faint)",
          background: "var(--color-elevated)", borderRadius: 6,
          padding: "4px 10px",
        }}>
          READ CAREFULLY
        </div>
      </div>

      {/* PDF */}
      <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
        <iframe
          src={pdfUrl}
          style={{ width: "100%", height: "100%", border: "none", display: "block" }}
          title={`${display} — Compliance Agreement`}
        />
      </div>

      {/* Confirm bar */}
      <div style={{
        flexShrink: 0,
        background: "var(--color-surface)",
        borderTop: "1px solid var(--color-border)",
        padding: "14px 20px 20px",
        paddingBottom: "calc(14px + env(safe-area-inset-bottom))",
      }}>
        <p style={{
          fontSize: 12, color: "var(--color-text-faint)", marginBottom: 12, lineHeight: 1.5, textAlign: "center",
        }}>
          By tapping below you confirm you have read, understood, and agree to the terms of this agreement.
        </p>
        <button
          onClick={handleConfirm}
          style={{
            width: "100%",
            background: scrolled ? "var(--color-lime)" : "var(--color-elevated)",
            border: "none", borderRadius: 12, padding: "18px 20px",
            fontSize: 17, fontWeight: 700,
            color: scrolled ? "#000" : "var(--color-text-faint)",
            cursor: "pointer",
            transition: "background 0.3s, color 0.3s",
          }}
        >
          I Have Read and Agree
        </button>
        {!scrolled && (
          <p style={{ fontSize: 11, color: "var(--color-text-faint)", textAlign: "center", marginTop: 8 }}>
            Please review the document above first
          </p>
        )}
      </div>
    </div>
  )
}
