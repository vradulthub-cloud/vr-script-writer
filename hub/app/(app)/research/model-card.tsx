"use client"

import { type ModelProfile } from "@/lib/api"
import { scoreColor, modelPhotoUrl, RANK_COLOR } from "./model-utils"
import { Photo } from "./model-photo"

// ─── Model card (trending / priority) ────────────────────────────────────────

export function ModelCard({ name, photoSrc, statLine, score, rank, bookings, onView }: {
  name: string
  photoSrc: string
  statLine: string
  score?: number
  rank?: string
  bookings?: string
  onView: () => void
}) {
  const rankKey = (rank ?? "").toLowerCase()
  const rankColor = RANK_COLOR[rankKey] ?? "var(--color-text-faint)"
  const bookingCount = parseInt(bookings ?? "0") || 0

  return (
    <div
      onClick={onView}
      style={{
        overflow: "hidden",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        display: "flex", flexDirection: "column",
        cursor: "pointer",
      }}
      className="hover:border-[--color-text-faint] transition-colors"
    >
      {/* Photo */}
      <div style={{ position: "relative", flexShrink: 0 }}>
        <Photo src={photoSrc} fallbackSrc={modelPhotoUrl(name)} name={name} width="100%" height={180} radius={0} objectPos="50% 15%" />

        {score !== undefined && (
          <div
            title={`Opportunity score: ${score}/100 — composite of booking recency, scene count, and agency tier`}
            style={{
              position: "absolute", top: 6, right: 6,
              background: scoreColor(score), color: "#000",
              borderRadius: 10, padding: "2px 7px",
              fontSize: 10, fontWeight: 700, lineHeight: "16px",
              cursor: "help",
            }}
          >
            {score}
          </div>
        )}

        {/* Gradient overlay */}
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0,
          background: "linear-gradient(transparent, rgba(0,0,0,0.85))",
          padding: "28px 8px 8px",
        }}>
          <div style={{
            fontSize: 12, fontWeight: 700, color: "var(--color-text)",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {name}
          </div>
          <div style={{
            fontSize: 10, color: "rgba(255,255,255,0.6)", marginTop: 1,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {statLine}
          </div>
        </div>
      </div>

      {/* Footer: rank pill + booking count */}
      <div style={{
        padding: "6px 10px",
        borderTop: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "var(--color-base)",
      }}>
        {rankKey ? (
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
            color: rankColor,
            background: `color-mix(in srgb, ${rankColor} 12%, transparent)`,
            border: `1px solid color-mix(in srgb, ${rankColor} 25%, transparent)`,
            padding: "2px 7px",
          }}>
            {rankKey}
          </span>
        ) : <span />}
        <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
          {bookingCount > 0 ? `${bookingCount}× booked` : "Never booked"}
        </span>
      </div>
    </div>
  )
}

// ─── Scene card ───────────────────────────────────────────────────────────────

export function SceneCard({ scene }: { scene: ModelProfile["slr_scenes"][0] }) {
  return (
    <div style={{
      display: "flex", gap: 10,
      padding: "10px 0",
      borderBottom: "1px solid var(--color-border-subtle)",
    }}>
      {/* Thumb */}
      {scene.thumb ? (
        <a href={scene.url || undefined} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0 }}>
          <img
            src={scene.thumb} alt=""
            referrerPolicy="no-referrer"
            crossOrigin="anonymous"
            style={{ width: 120, height: 68, objectFit: "cover", borderRadius: 4, display: "block" }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = "none" }}
          />
        </a>
      ) : (
        <div style={{
          width: 120, height: 68, borderRadius: 4,
          background: "var(--color-elevated)", flexShrink: 0,
        }} />
      )}

      {/* Info */}
      <div style={{ minWidth: 0, flex: 1 }}>
        {scene.url ? (
          <a
            href={scene.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)", textDecoration: "none",
                     display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" } as React.CSSProperties}
          >
            {scene.title}
          </a>
        ) : (
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)" }}>
            {scene.title}
          </div>
        )}

        <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 3 }}>
          {[scene.studio && `🎬 ${scene.studio}`, scene.date && `📅 ${scene.date}`, scene.duration && `⏱ ${scene.duration}`]
            .filter(Boolean).join("  ·  ")}
        </div>
        {(scene.views || scene.likes || scene.comments) && (
          <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
            {[scene.views && `👁 ${scene.views}`, scene.likes && `❤️ ${scene.likes}`, scene.comments && `💬 ${scene.comments}`]
              .filter(Boolean).join("  ·  ")}
          </div>
        )}
      </div>
    </div>
  )
}
