"use client"

import Link from "next/link"
import { type Scene, type Script } from "@/lib/api"
import { STUDIO_COLOR, STUDIO_ABBR } from "@/lib/studio-colors"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

interface Props {
  recentScenes: Scene[]
  missingTotal: number
  scripts: Script[]
  idToken?: string | undefined
}

export function TriageFeed({ recentScenes, scripts }: Props) {
  const byStudio = STUDIOS
    .map(s => ({
      studio: s,
      abbr: STUDIO_ABBR[s] ?? s,
      color: STUDIO_COLOR[s] ?? "var(--color-text-muted)",
      scenes: recentScenes.filter(sc => sc.studio === s).slice(0, 5),
    }))
    .filter(g => g.scenes.length > 0)

  const hasAnything = byStudio.length > 0 || scripts.length > 0

  return (
    <Section title="Recent Scenes" subtitle={hasAnything ? undefined : "No recent scenes found."}>
      {byStudio.map(group => (
        <div key={group.studio}>
          <div style={{
            padding: "7px 14px",
            display: "flex", alignItems: "baseline", gap: 8,
            borderBottom: "1px solid var(--color-border-subtle)",
            background: "var(--color-base)",
          }}>
            <Link
              href="/missing"
              style={{
                fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
                color: group.color, textDecoration: "none",
              }}
              className="hover:opacity-80"
            >
              {group.abbr}
            </Link>
            <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{group.studio}</span>
          </div>
          {group.scenes.map((scene, i) => {
            const dateStr = (scene.release_date ?? "").slice(0, 10)
            return (
              <Link
                key={scene.id}
                href={`/missing?scene=${encodeURIComponent(scene.id)}`}
                style={{
                  padding: "7px 14px",
                  borderBottom: i < group.scenes.length - 1 ? "1px solid var(--color-border-subtle)" : "none",
                  display: "flex", alignItems: "center", gap: 10,
                  textDecoration: "none", color: "inherit",
                }}
                className="hover:bg-[--color-elevated]"
              >
                <span style={{
                  fontSize: 11, fontFamily: "var(--font-mono)", color: group.color,
                  flexShrink: 0, fontWeight: 600,
                }}>
                  {scene.id}
                </span>
                <span style={{
                  fontSize: 12, color: "var(--color-text)",
                  flex: "1 1 auto", minWidth: 0,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {scene.title || scene.performers || <span style={{ color: "var(--color-text-faint)", fontStyle: "italic" }}>—</span>}
                </span>
                {dateStr && (
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                    {dateStr}
                  </span>
                )}
              </Link>
            )
          })}
        </div>
      ))}

      {scripts.length > 0 && (
        <div>
          <div style={{
            padding: "7px 14px",
            display: "flex", alignItems: "baseline", gap: 8,
            borderBottom: "1px solid var(--color-border-subtle)",
            borderTop: byStudio.length > 0 ? "1px solid var(--color-border)" : undefined,
            background: "var(--color-base)",
          }}>
            <Link
              href="/scripts"
              style={{
                fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
                color: "var(--color-text-muted)", textDecoration: "none",
              }}
              className="hover:text-[--color-text]"
            >
              Scripts Queued
            </Link>
            <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
              · {scripts.length}
            </span>
          </div>
          {scripts.slice(0, 5).map((script, i) => {
            const color = STUDIO_COLOR[script.studio] ?? "var(--color-text-muted)"
            const abbr = STUDIO_ABBR[script.studio] ?? script.studio
            const talent = [script.female, script.male].filter(Boolean).join(" / ")
            return (
              <div
                key={script.id}
                style={{
                  padding: "8px 14px",
                  borderBottom: i < Math.min(scripts.length, 5) - 1 ? "1px solid var(--color-border-subtle)" : "none",
                  display: "flex", alignItems: "center", gap: 10,
                }}
              >
                <span style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                  padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                  background: `color-mix(in srgb, ${color} 14%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${color} 26%, transparent)`,
                  color,
                }}>{abbr}</span>
                <span style={{ fontSize: 12, color: "var(--color-text)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {talent || "—"}
                </span>
                {script.shoot_date && (
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                    {script.shoot_date}
                  </span>
                )}
                <Link
                  href="/scripts"
                  style={{
                    padding: "3px 10px", borderRadius: 3, fontSize: 11, fontWeight: 500,
                    textDecoration: "none",
                    background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                    color: "var(--color-lime)",
                    border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                    flexShrink: 0,
                  }}
                >
                  Start
                </Link>
              </div>
            )
          })}
          {scripts.length > 5 && (
            <Link
              href="/scripts"
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                minHeight: 44, padding: "0 14px",
                fontSize: 11, color: "var(--color-text-muted)", textDecoration: "none",
              }}
              className="hover:bg-[--color-elevated]"
            >
              See all {scripts.length} →
            </Link>
          )}
        </div>
      )}
    </Section>
  )
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "9px 14px", borderBottom: "1px solid var(--color-border)" }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {subtitle && (
          <p style={{ margin: "3px 0 0", fontSize: 11, color: "var(--color-text-faint)" }}>{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  )
}
