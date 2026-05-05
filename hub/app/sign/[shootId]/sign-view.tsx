"use client"

import { useState, useEffect } from "react"
import { CheckCircle2, HelpCircle } from "lucide-react"

const STUDIO_COLOR: Record<string, string> = {
  FuckPassVR: "#f97316",
  VRHush:     "#8b5cf6",
  VRAllure:   "#ec4899",
  NaughtyJOI: "#3b82f6",
}

const READ_SECONDS = 30

interface Props {
  shootId: string
  talent: string    // slug, e.g. "SofiaRed"
  display: string   // pretty name, e.g. "Sofia Red"
  studio: string    // e.g. "VRHush"
}

export function SignView({ shootId, talent, display, studio }: Props) {
  const [confirmed, setConfirmed] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  const [secondsRead, setSecondsRead] = useState(0)
  const accent = STUDIO_COLOR[studio] ?? "var(--color-lime)"

  useEffect(() => {
    if (secondsRead >= READ_SECONDS) return
    const t = setInterval(() => setSecondsRead(s => Math.min(READ_SECONDS, s + 1)), 1000)
    return () => clearInterval(t)
  }, [secondsRead])

  const readEnough = secondsRead >= READ_SECONDS
  const canConfirm = readEnough && acknowledged

  function handleConfirm() {
    if (!canConfirm) return
    setConfirmed(true)
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
        <div style={{ textAlign: "center", maxWidth: 360 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text)", marginBottom: 8 }}>
            Agreement confirmed
          </div>
          <div style={{ fontSize: 15, color: "var(--color-text-faint)", lineHeight: 1.5 }}>
            Thank you, {display}. Your signature has been recorded.
            <br />You may close this tab and hand the phone back.
          </div>
        </div>
        <button
          onClick={() => window.close()}
          style={{
            marginTop: 8,
            background: "transparent",
            border: "1px solid var(--color-border)",
            borderRadius: 10,
            padding: "12px 24px", fontSize: 14, fontWeight: 600,
            color: "var(--color-text-muted)", cursor: "pointer",
          }}
        >
          Close tab
        </button>
      </div>
    )
  }

  const secondsLeft = READ_SECONDS - secondsRead
  const readPct = Math.round((secondsRead / READ_SECONDS) * 100)

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
        padding: "14px 20px 16px",
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: "0.16em",
          textTransform: "uppercase", color: accent, marginBottom: 4,
        }}>
          {studio || "Performer Agreement"}
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--color-text)", marginBottom: 6 }}>
          {display}
        </div>
        <div style={{ fontSize: 13, color: "var(--color-text-muted)", lineHeight: 1.5 }}>
          This is your performer agreement for today&apos;s shoot. It covers the services agreement,
          federal 2257 records, and the model release. Please read it fully before signing.
        </div>
      </div>

      {/* PDF */}
      <div style={{ flex: 1, overflow: "hidden", position: "relative", background: "var(--color-base)" }}>
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

        {/* Read-time indicator — counts UP, framed as reading time FOR them */}
        {!readEnough && (
          <div style={{ marginBottom: 12 }}>
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              fontSize: 11, color: "var(--color-text-faint)", marginBottom: 6,
            }}>
              <span>Reading time</span>
              <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                0:{String(secondsLeft).padStart(2, "0")} remaining
              </span>
            </div>
            <div style={{
              height: 4, background: "var(--color-elevated)", borderRadius: 2, overflow: "hidden",
            }}>
              <div style={{
                height: "100%", width: "100%", background: accent,
                transformOrigin: "left",
                transform: `scaleX(${readPct / 100})`,
                transition: "transform 1s linear",
              }} />
            </div>
          </div>
        )}

        {/* Acknowledge checkbox */}
        <label
          style={{
            display: "flex", alignItems: "flex-start", gap: 10,
            padding: "10px 12px",
            background: acknowledged ? "rgba(190,214,47,0.06)" : "var(--color-elevated)",
            border: `1px solid ${acknowledged ? "rgba(190,214,47,0.3)" : "var(--color-border)"}`,
            borderRadius: 10, marginBottom: 10, cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={e => setAcknowledged(e.target.checked)}
            style={{
              width: 18, height: 18, marginTop: 1, flexShrink: 0,
              accentColor: "var(--color-lime)", cursor: "pointer",
            }}
          />
          <span style={{ fontSize: 13, color: "var(--color-text)", lineHeight: 1.45 }}>
            I have read this agreement and understand what I am signing.
          </span>
        </label>

        {/* Sign button */}
        <button
          onClick={handleConfirm}
          disabled={!canConfirm}
          style={{
            width: "100%",
            background: canConfirm ? "var(--color-lime)" : "var(--color-elevated)",
            border: "none", borderRadius: 12, padding: "18px 20px",
            fontSize: 16, fontWeight: 700,
            color: canConfirm ? "#000" : "var(--color-text-faint)",
            cursor: canConfirm ? "pointer" : "not-allowed",
            transition: "background 0.2s, color 0.2s",
          }}
        >
          {canConfirm
            ? "Sign & Confirm Agreement"
            : !readEnough && !acknowledged
              ? "Read the document to continue"
              : !readEnough
                ? `Keep reading · ${secondsLeft}s`
                : "Check the box above to sign"
          }
        </button>

        {/* Help affordance */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          marginTop: 12, fontSize: 12, color: "var(--color-text-faint)",
        }}>
          <HelpCircle size={13} aria-hidden="true" />
          <span>Questions about this agreement? Ask your director before signing.</span>
        </div>
      </div>
    </div>
  )
}
