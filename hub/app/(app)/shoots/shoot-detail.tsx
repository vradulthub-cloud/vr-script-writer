"use client"

import { useState, useEffect } from "react"
import { createPortal } from "react-dom"
import { X, RefreshCcw, Wand2, Check, FileText } from "lucide-react"
import Link from "next/link"
import { statusColor, STATUS_LABEL, cellApplies, formatShootDate } from "./shoot-utils"
import { api, SHOOT_ASSET_LABELS, type Shoot, type BoardShootScene, type AssetType } from "@/lib/api"
import { revalidateAfterWrite } from "@/lib/cache-actions"
import { TAG_SCENES, TAG_SHOOTS } from "@/lib/cache-tags"
import { studioColor } from "@/lib/studio-colors"
import { formatApiError } from "@/lib/errors"

// ── Scene asset table ─────────────────────────────────────────────────

function SceneAssetTable({
  scene,
  idToken,
  onRevalidate,
}: {
  scene: BoardShootScene
  idToken?: string
  onRevalidate: (assetType: AssetType) => Promise<void>
}) {
  const color = studioColor(scene.studio)
  const [title, setTitle] = useState(scene.title)
  const [genTitle, setGenTitle] = useState("")
  const [genBusy, setGenBusy] = useState<"idle" | "loading" | "saving">("idle")
  const [genErr, setGenErr] = useState<string | null>(null)

  const canGenerate = !!scene.scene_id

  async function runGenerate() {
    if (!scene.scene_id) return
    setGenBusy("loading")
    setGenErr(null)
    try {
      const { title: t } = await api(idToken ?? null).scenes.generateTitle(scene.scene_id, {})
      setGenTitle(t)
    } catch (e) {
      setGenErr(formatApiError(e, "Title"))
    } finally {
      setGenBusy("idle")
    }
  }

  async function runApply() {
    if (!scene.scene_id || !genTitle) return
    setGenBusy("saving")
    try {
      await api(idToken ?? null).scenes.updateTitle(scene.scene_id, genTitle)
      void revalidateAfterWrite([TAG_SCENES])
      setTitle(genTitle)
      setGenTitle("")
    } catch (e) {
      setGenErr(formatApiError(e, "Save"))
    } finally {
      setGenBusy("idle")
    }
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div className="flex items-center gap-2 mb-2">
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.05em",
            color,
            textTransform: "uppercase",
          }}
        >
          {scene.studio} · {scene.scene_type}
        </span>
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
          {scene.scene_id || "(pending Grail row)"}
        </span>
      </div>

      <div
        className="flex items-center gap-2 mb-2"
        style={{
          padding: "6px 8px",
          borderRadius: 4,
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
        }}
      >
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600, flexShrink: 0 }}>
          Title
        </span>
        <span style={{ flex: 1, fontSize: 12, color: title ? "var(--color-text)" : "var(--color-text-faint)", fontStyle: title ? "normal" : "italic", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {title || "—"}
        </span>
        <button
          onClick={runGenerate}
          disabled={!canGenerate || genBusy !== "idle"}
          title={canGenerate ? "Generate title from script" : "Scene needs a Grail row first"}
          aria-label="Generate title"
          style={{
            flexShrink: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            padding: "2px 7px",
            borderRadius: 3,
            background: "transparent",
            color: !canGenerate ? "var(--color-text-faint)" : genBusy === "loading" ? "var(--color-text-faint)" : color,
            border: `1px solid ${!canGenerate ? "var(--color-border)" : `color-mix(in srgb, ${color} 35%, transparent)`}`,
            cursor: !canGenerate || genBusy !== "idle" ? "not-allowed" : "pointer",
          }}
        >
          <Wand2 size={10} aria-hidden="true" />
          {genBusy === "loading" ? "…" : "Generate"}
        </button>
      </div>

      {(genTitle || genErr) && (
        <div
          className="flex items-center gap-2 mb-2"
          style={{
            padding: "6px 8px",
            borderRadius: 4,
            background: "var(--color-elevated)",
            border: `1px solid color-mix(in srgb, ${color} 30%, var(--color-border))`,
          }}
        >
          {genErr ? (
            <>
              <span style={{ flex: 1, fontSize: 11, color: "var(--color-err)" }}>{genErr}</span>
              <button onClick={() => { setGenErr(null); setGenTitle("") }} aria-label="Dismiss" style={{ color: "var(--color-text-faint)" }}>
                <X size={11} aria-hidden="true" />
              </button>
            </>
          ) : (
            <>
              <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: "var(--color-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={genTitle}>
                {genTitle}
              </span>
              <button
                onClick={runApply}
                disabled={genBusy === "saving"}
                aria-label="Apply title"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 3,
                  fontSize: 10,
                  padding: "2px 7px",
                  borderRadius: 3,
                  background: "var(--color-lime)",
                  color: "var(--color-lime-ink)",
                  fontWeight: 600,
                  border: "none",
                  cursor: genBusy === "saving" ? "wait" : "pointer",
                }}
              >
                <Check size={10} aria-hidden="true" />
                {genBusy === "saving" ? "…" : "Apply"}
              </button>
              <button
                onClick={() => setGenTitle("")}
                aria-label="Discard"
                style={{
                  fontSize: 10,
                  padding: "2px 6px",
                  borderRadius: 3,
                  background: "transparent",
                  color: "var(--color-text-faint)",
                  border: "1px solid var(--color-border)",
                  cursor: "pointer",
                }}
              >
                Discard
              </button>
            </>
          )}
        </div>
      )}

      <div
        className="flex items-center gap-2 mb-2"
        style={{
          padding: "6px 8px",
          borderRadius: 4,
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
        }}
      >
        <span style={{ fontSize: 10, color: "var(--color-text-faint)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600, flexShrink: 0 }}>
          Description
        </span>
        <span style={{ flex: 1, fontSize: 12, color: scene.has_description ? "var(--color-text)" : "var(--color-text-faint)", fontStyle: scene.has_description ? "normal" : "italic" }}>
          {scene.has_description ? "Done" : "—"}
        </span>
        {!scene.has_description && scene.scene_id && (
          <Link
            href={`/descriptions?scene=${encodeURIComponent(scene.scene_id)}`}
            style={{
              flexShrink: 0,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 10,
              padding: "2px 7px",
              borderRadius: 3,
              background: "transparent",
              color: color,
              border: `1px solid color-mix(in srgb, ${color} 35%, transparent)`,
              textDecoration: "none",
            }}
          >
            <FileText size={10} aria-hidden="true" />
            Write
          </Link>
        )}
      </div>

      <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <tbody>
          {scene.assets.filter(a => cellApplies(a.asset_type, scene.scene_type)).map(a => {
            const hasWarn = a.validity.some(v => v.status === "warn")
            const cellColor = statusColor(a.status, hasWarn)
            return (
              <tr
                key={a.asset_type}
                style={{ borderBottom: "1px solid var(--color-border)" }}
              >
                <td style={{ padding: "6px 4px", fontSize: 11, color: "var(--color-text)" }}>
                  {SHOOT_ASSET_LABELS[a.asset_type]}
                </td>
                <td style={{ padding: "6px 4px", fontSize: 11, color: cellColor, fontWeight: 500 }}>
                  {STATUS_LABEL[a.status]}{hasWarn ? ` · ${a.validity.length} note${a.validity.length === 1 ? "" : "s"}` : ""}
                </td>
                <td style={{ padding: "6px 4px", fontSize: 10, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)", textAlign: "right" }}>
                  {a.validated_at ? a.validated_at.slice(5, 16).replace("T", " ") : ""}
                </td>
                <td style={{ padding: "6px 0 6px 6px", textAlign: "right" }}>
                  <button
                    onClick={() => { void onRevalidate(a.asset_type) }}
                    aria-label={`Recheck ${a.asset_type}`}
                    style={{
                      fontSize: 10,
                      color: "var(--color-text-muted)",
                      background: "transparent",
                      border: "1px solid var(--color-border)",
                      borderRadius: 3,
                      padding: "2px 6px",
                      cursor: "pointer",
                    }}
                  >
                    <RefreshCcw size={9} className="inline" aria-hidden="true" />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Shoot detail panel ────────────────────────────────────────────────

interface ShootDetailProps {
  shoot: Shoot
  idToken?: string
  onClose: () => void
  onRevalidate: (position: number, assetType: AssetType) => Promise<void>
}

export function ShootDetail({ shoot, idToken, onClose, onRevalidate }: ShootDetailProps) {
  const color = studioColor(shoot.scenes[0]?.studio ?? "FuckPassVR")
  return (
    <div
      role="complementary"
      aria-label={`Shoot ${shoot.shoot_id} details`}
      style={{
        display: "flex",
        flexDirection: "column",
        maxHeight: "calc(100vh - var(--spacing-topbar) - 24px)",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "14px",
          borderBottom: "1px solid var(--color-border)",
          background: `color-mix(in srgb, ${color} 6%, var(--color-surface))`,
          flexShrink: 0,
        }}
      >
        <div className="flex items-center justify-between mb-1">
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            {formatShootDate(shoot.shoot_date)} · {shoot.source_tab}
          </div>
          <button onClick={onClose} aria-label="Close" style={{ color: "var(--color-text-muted)" }}>
            <X size={14} />
          </button>
        </div>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "var(--color-text)" }}>
          {shoot.female_talent}
          {shoot.male_talent && (
            <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}> / {shoot.male_talent}</span>
          )}
        </h2>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
          {shoot.female_agency || "—"}
          {shoot.male_agency && <> · {shoot.male_agency}</>}
        </div>
        {shoot.location && (
          <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 2 }}>
            {shoot.location}{shoot.home_owner ? ` · host: ${shoot.home_owner}` : ""}
          </div>
        )}
      </div>

      <div style={{ padding: "10px 14px", overflowY: "auto" }}>
        {shoot.scenes.map(scene => (
          <SceneAssetTable
            key={scene.position}
            scene={scene}
            idToken={idToken}
            onRevalidate={(at) => onRevalidate(scene.position, at)}
          />
        ))}
      </div>
    </div>
  )
}

// ── Shoot details modal ───────────────────────────────────────────────

export function ShootDetailsModal({
  shoot,
  idToken,
  onClose,
  onRevalidate,
}: {
  shoot: Shoot
  idToken?: string
  onClose: () => void
  onRevalidate: (position: number, assetType: AssetType) => Promise<void>
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

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Shoot ${shoot.shoot_id} details`}
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
          width: "min(820px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
        }}
      >
        <ShootDetail
          shoot={shoot}
          idToken={idToken}
          onClose={onClose}
          onRevalidate={onRevalidate}
        />
      </div>
    </div>,
    document.body,
  )
}
