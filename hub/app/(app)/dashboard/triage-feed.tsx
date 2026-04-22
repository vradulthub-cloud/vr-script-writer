"use client"

import Link from "next/link"
import { type Scene, type Script } from "@/lib/api"
import { STUDIO_COLOR, STUDIO_ABBR } from "@/lib/studio-colors"
import { AssetCells, type AssetCell } from "@/components/ui/asset-cells"

const ASSET_COLS = [
  { key: "has_description" as const, label: "Desc" },
  { key: "has_videos"      as const, label: "Videos" },
  { key: "has_thumbnail"   as const, label: "Thumb" },
  { key: "has_photos"      as const, label: "Photos" },
  { key: "has_storyboard"  as const, label: "Story" },
]

function sceneAssetCells(scene: Scene): AssetCell[] {
  return ASSET_COLS.map(a => ({
    label: a.label,
    status: scene[a.key] ? "ok" as const : "missing" as const,
  }))
}

interface Props {
  missingScenes: Scene[]
  missingTotal: number
  scripts: Script[]
  /** Kept on the prop list so dashboard/page.tsx doesn't have to thread it
   *  conditionally; not used inside the feed today since the Approvals
   *  subsection (which needed it) was removed when the team paused that
   *  workflow. Reintroduce when approvals come back. */
  idToken?: string | undefined
}

/**
 * Triage feed — what's "Waiting on You" today.
 *
 * The Approvals subsection used to live here (with its own optimistic
 * decide / undo / commit logic). It was removed when the team paused the
 * approvals workflow — keeping a "Waiting on You" card pointing at an
 * empty list is worse than not showing the card. The full prior version
 * lives in git if approvals come back.
 */
export function TriageFeed({
  missingScenes,
  missingTotal,
  scripts,
}: Props) {
  const hasAnything = missingScenes.length > 0 || scripts.length > 0

  return (
    <Section title="Waiting on You" subtitle={hasAnything ? undefined : "Nothing blocking — inbox clear."}>
      {/* Grail Assets */}
      <SubSection
        label="Grail Assets"
        count={missingTotal}
        href="/missing"
        emptyLabel="All assets accounted for ✓"
        empty={missingScenes.length === 0}
      >
        {missingScenes.slice(0, 5).map(scene => {
          const color = STUDIO_COLOR[scene.studio] ?? "var(--color-text-muted)"
          const abbr = STUDIO_ABBR[scene.studio] ?? scene.studio
          const cells = sceneAssetCells(scene)
          const dateStr = (scene.release_date ?? "").slice(0, 10)
          return (
            <Link
              key={scene.id}
              href={`/missing?scene=${encodeURIComponent(scene.id)}`}
              style={{
                padding: "8px 14px",
                borderBottom: "1px solid var(--color-border-subtle)",
                display: "flex", alignItems: "center", gap: 10,
                textDecoration: "none", color: "inherit",
              }}
              className="hover:bg-[--color-elevated]"
            >
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                background: `color-mix(in srgb, ${color} 14%, transparent)`,
                border: `1px solid color-mix(in srgb, ${color} 26%, transparent)`,
                color,
              }}>{abbr}</span>

              <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--color-text)", flexShrink: 0 }}>
                {scene.id}
              </span>

              <span
                title={scene.performers || undefined}
                style={{
                  fontSize: 12,
                  color: "var(--color-text)",
                  fontWeight: 500,
                  minWidth: 0,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: "1 1 auto",
                }}
              >
                {scene.performers || <span style={{ color: "var(--color-text-faint)", fontStyle: "italic" }}>—</span>}
              </span>

              <span style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>
                <AssetCells cells={cells} />
              </span>

              {dateStr && (
                <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                  {dateStr}
                </span>
              )}
            </Link>
          )
        })}
        {missingTotal > missingScenes.length && (
          <SeeAll href="/missing" label={`See all ${missingTotal} →`} />
        )}
      </SubSection>

      {/* Scripts Queued — only rendered when non-empty */}
      {scripts.length > 0 && (
        <SubSection label="Scripts Queued" count={scripts.length} href="/scripts" empty={false}>
          {scripts.slice(0, 5).map(script => {
            const color = STUDIO_COLOR[script.studio] ?? "var(--color-text-muted)"
            const abbr = STUDIO_ABBR[script.studio] ?? script.studio
            const talent = [script.female, script.male].filter(Boolean).join(" / ")
            return (
              <div
                key={script.id}
                style={{
                  padding: "8px 14px",
                  borderBottom: "1px solid var(--color-border-subtle)",
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
          {scripts.length > 5 && <SeeAll href="/scripts" label={`See all ${scripts.length} →`} />}
        </SubSection>
      )}
    </Section>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

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

function SubSection({
  label,
  count,
  href,
  emptyLabel,
  empty,
  children,
}: {
  label: string
  count: number
  href: string
  emptyLabel?: string
  empty: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <div style={{
        padding: "7px 14px",
        display: "flex", alignItems: "baseline", gap: 8,
        borderBottom: empty ? "none" : "1px solid var(--color-border-subtle)",
        background: "var(--color-base)",
      }}>
        <Link
          href={href}
          style={{
            fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
            color: "var(--color-text-muted)", textDecoration: "none",
          }}
          className="hover:text-[--color-text]"
        >
          {label}
        </Link>
        <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
          · {count}
        </span>
      </div>
      {empty ? (
        <div style={{ padding: "10px 14px", fontSize: 11, color: "var(--color-text-faint)" }}>
          {emptyLabel}
        </div>
      ) : (
        children
      )}
    </div>
  )
}

function SeeAll({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 44,
        padding: "0 14px",
        fontSize: 11,
        color: "var(--color-text-muted)",
        textDecoration: "none",
      }}
      className="hover:bg-[--color-elevated]"
    >
      {label}
    </Link>
  )
}
