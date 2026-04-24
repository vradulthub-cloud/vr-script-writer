"use client"

import { useState, type ReactNode } from "react"

export type TabKey = "users" | "system" | "activity" | "prompts"

interface TabDef {
  key: TabKey
  label: string
  badge?: string | number
  description: string
}

interface AdminTabsProps {
  /** Tab content rendered as siblings — only the active one is shown. Keeping
   *  all four mounted would re-fetch on every switch and lose editor drafts;
   *  swapping by `display: none` keeps state across switches without remount.
   */
  panels: Record<TabKey, ReactNode>
  /** Optional badge counts shown next to tab labels (e.g. user count, task count). */
  badges?: Partial<Record<TabKey, string | number>>
  /** Initial tab. Defaults to "users". */
  initial?: TabKey
}

const TABS: TabDef[] = [
  { key: "users",    label: "Users",      description: "Roles & tab access" },
  { key: "system",   label: "System",     description: "Health, syncs, system check" },
  { key: "activity", label: "Activity",   description: "Background tasks & audit log" },
  { key: "prompts",  label: "AI Prompts", description: "Edit description / title / script generation" },
]

export function AdminTabs({ panels, badges, initial = "users" }: AdminTabsProps) {
  const [active, setActive] = useState<TabKey>(initial)
  const activeMeta = TABS.find(t => t.key === active)

  return (
    <div>
      {/* Tab strip — sticky-ish so it stays anchored above the panel content. */}
      <nav
        role="tablist"
        aria-label="Admin sections"
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid var(--color-border)",
          marginBottom: 0,
        }}
      >
        {TABS.map(tab => {
          const isActive = tab.key === active
          const badge = badges?.[tab.key]
          return (
            <button
              key={tab.key}
              role="tab"
              type="button"
              aria-selected={isActive}
              onClick={() => setActive(tab.key)}
              style={{
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${isActive ? "var(--color-lime)" : "transparent"}`,
                color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
                fontSize: 12,
                fontWeight: isActive ? 700 : 500,
                letterSpacing: "0.04em",
                padding: "12px 18px",
                cursor: "pointer",
                fontFamily: "inherit",
                position: "relative",
                top: 1,                  // overlap the parent border
                display: "flex",
                alignItems: "center",
                gap: 8,
                transition: "color 120ms ease",
              }}
            >
              {tab.label}
              {badge !== undefined && badge !== "" && (
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "1px 6px",
                    borderRadius: 8,
                    background: isActive
                      ? "color-mix(in srgb, var(--color-lime) 18%, transparent)"
                      : "var(--color-elevated)",
                    color: isActive ? "var(--color-lime)" : "var(--color-text-faint)",
                    fontVariantNumeric: "tabular-nums",
                    border: `1px solid ${isActive ? "color-mix(in srgb, var(--color-lime) 30%, transparent)" : "var(--color-border-subtle)"}`,
                  }}
                >
                  {badge}
                </span>
              )}
            </button>
          )
        })}
        <div style={{ flex: 1 }} />
        {activeMeta && (
          <span
            style={{
              alignSelf: "center",
              padding: "0 4px",
              fontSize: 10,
              color: "var(--color-text-faint)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            {activeMeta.description}
          </span>
        )}
      </nav>

      <div style={{ paddingTop: 20 }}>
        {/* All four are rendered but only the active one is visible. Keeps
            scroll position + form state across tab switches. */}
        {(Object.keys(panels) as TabKey[]).map(key => (
          <div
            key={key}
            role="tabpanel"
            hidden={key !== active}
            aria-hidden={key !== active}
            style={{ display: key === active ? "block" : "none" }}
          >
            {panels[key]}
          </div>
        ))}
      </div>
    </div>
  )
}
