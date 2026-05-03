"use client"

import { useState, useEffect } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import { statusColor, STATUS_LABEL } from "./shoot-utils"
import { SHOOT_ASSET_LABELS, type Shoot, type AssetType } from "@/lib/api"

function MetaRow({ label, value, mono, valueColor }: { label: string; value: string; mono?: boolean; valueColor?: string }) {
  return (
    <>
      <span
        style={{
          color: "var(--color-text-faint)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          fontSize: 9,
          fontWeight: 700,
          alignSelf: "center",
        }}
      >
        {label}
      </span>
      <span
        style={{
          color: valueColor ?? "var(--color-text)",
          fontFamily: mono ? "var(--font-mono)" : undefined,
          fontSize: 12,
          fontWeight: valueColor ? 700 : 500,
        }}
      >
        {value}
      </span>
    </>
  )
}

interface ValidityPopoverProps {
  shoot: Shoot
  position: number
  assetType: AssetType
  onClose: () => void
  onRevalidate: () => Promise<void>
}

export function ValidityPopover({ shoot, position, assetType, onClose, onRevalidate }: ValidityPopoverProps) {
  const scene = shoot.scenes.find(s => s.position === position)
  const state = scene?.assets.find(a => a.asset_type === assetType)
  const [busy, setBusy] = useState(false)
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  if (!scene || !state || !mounted) return null

  const accent = statusColor(state.status, state.validity.some(v => v.status === "warn"))

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="asset-modal-title"
      onClick={onClose}
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
          width: "min(480px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
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
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: accent,
                marginBottom: 6,
              }}
            >
              {scene.studio} · {scene.scene_type} · {scene.scene_id || "pending Grail"}
            </div>
            <h2
              id="asset-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 400,
                fontSize: 22,
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              {SHOOT_ASSET_LABELS[assetType]}
            </h2>
          </div>
          <button
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

        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 14, overflowY: "auto", flex: "1 1 auto" }}>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 12, rowGap: 4, fontSize: 11 }}>
            <MetaRow label="Status" value={STATUS_LABEL[state.status]} valueColor={accent} />
            {state.first_seen_at && <MetaRow label="First seen" value={state.first_seen_at.slice(0, 19)} mono />}
            {state.validated_at && <MetaRow label="Validated" value={state.validated_at.slice(0, 19)} mono />}
          </div>

          <div>
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--color-text-faint)",
                marginBottom: 6,
              }}
            >
              Validity checks
            </div>
            {state.validity.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: 0, lineHeight: 1.5 }}>
                {state.status === "validated"
                  ? "All checks passed."
                  : state.status === "not_present"
                    ? "Not yet uploaded to MEGA."
                    : "No validity issues to report."}
              </p>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                {state.validity.map((v, i) => {
                  const color = v.status === "fail" ? "var(--color-err)" : v.status === "warn" ? "var(--color-warn)" : "var(--color-ok)"
                  return (
                    <li
                      key={i}
                      style={{
                        padding: "8px 10px",
                        fontSize: 12,
                        color,
                        background: `color-mix(in srgb, ${color} 8%, transparent)`,
                        border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
                      }}
                    >
                      <strong style={{ fontWeight: 700 }}>{v.check}</strong>: {v.message}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            background: "var(--color-surface)",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: "pointer",
            }}
          >
            Close
          </button>
          <button
            onClick={async () => { setBusy(true); try { await onRevalidate() } finally { setBusy(false) } }}
            disabled={busy}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-lime)",
              color: "var(--color-lime-ink)",
              border: "1px solid var(--color-lime)",
              opacity: busy ? 0.6 : 1,
              cursor: busy ? "wait" : "pointer",
            }}
          >
            {busy ? "Checking…" : "Retry check"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
