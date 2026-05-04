"use client"

/**
 * Compliance page shell — owns the top-level tab toggle between the
 * on-set Wizard and the searchable Database view.
 *
 * The wizard is unchanged; we just gate it behind a tab. Once an admin
 * picks a shoot inside the wizard, the tab strip hides so the wizard's
 * sticky header (and the iPad-friendly paperwork flow) own the screen.
 */

import { useState } from "react"
import { ClipboardList, Database } from "lucide-react"
import type { ComplianceShoot } from "@/lib/api"
import { ComplianceView } from "./compliance-view"
import { ComplianceDatabase } from "./compliance-database"

type Tab = "wizard" | "database"

interface Props {
  initialShoots: ComplianceShoot[]
  initialDate: string
  idToken: string | undefined
  loadError: string | null
  initialTab?: Tab
}

export function ComplianceShell({
  initialShoots, initialDate, idToken, loadError, initialTab = "wizard",
}: Props) {
  const [tab, setTab] = useState<Tab>(initialTab)

  // We never *unmount* the wizard when switching tabs — its in-flight state
  // (selected shoot, captured photos, draft form values) would be discarded
  // and the iPad operator would lose work. Hide via display:none instead.
  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)" }}>
      <TabStrip tab={tab} onChange={setTab} />

      <div style={{ display: tab === "wizard" ? "block" : "none" }}>
        <ComplianceView
          initialShoots={initialShoots}
          initialDate={initialDate}
          idToken={idToken}
          loadError={loadError}
        />
      </div>

      {tab === "database" && (
        <div style={{ maxWidth: 1280, margin: "0 auto" }}>
          <ComplianceDatabase idToken={idToken} />
        </div>
      )}
    </div>
  )
}

function TabStrip({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  return (
    <div
      role="tablist"
      aria-label="Compliance views"
      style={{
        position: "sticky", top: 0, zIndex: 30,
        background: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        display: "flex",
        gap: 0,
        padding: "0 12px",
      }}
    >
      <TabButton
        active={tab === "wizard"}
        onClick={() => onChange("wizard")}
        icon={<ClipboardList size={14} />}
        label="Shoot Wizard"
        sub="On-set paperwork flow"
      />
      <TabButton
        active={tab === "database"}
        onClick={() => onChange("database")}
        icon={<Database size={14} />}
        label="Database"
        sub="Search every record"
      />
    </div>
  )
}

function TabButton({
  active, onClick, icon, label, sub,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  sub: string
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      style={{
        position: "relative",
        background: "transparent",
        border: "none",
        padding: "12px 18px 11px",
        cursor: "pointer",
        color: active ? "var(--color-text)" : "var(--color-text-faint)",
        display: "flex", alignItems: "center", gap: 8,
        fontFamily: "inherit",
        borderBottom: active
          ? "2px solid var(--color-lime)"
          : "2px solid transparent",
        marginBottom: -1,
      }}
    >
      <span style={{ color: active ? "var(--color-lime)" : "currentColor" }}>{icon}</span>
      <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 0 }}>
        <span style={{
          fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase",
        }}>
          {label}
        </span>
        <span style={{
          fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.02em",
        }}>
          {sub}
        </span>
      </span>
    </button>
  )
}
