"use client"

import { useState } from "react"
import { PageHeader } from "@/components/ui/page-header"

interface Props {
  pendingCount: number
  children: {
    review: React.ReactNode
    submit: React.ReactNode
  }
}

export function ApprovalsPageShell({ pendingCount, children }: Props) {
  const [tab, setTab] = useState<"review" | "submit">("review")

  return (
    <div>
      <PageHeader
        title="Approvals"
        eyebrow={tab === "review" ? (pendingCount > 0 ? `${pendingCount} pending review` : "queue clear") : "Submit for approval"}
        actions={
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <button
              onClick={() => setTab("review")}
              className="px-3 py-1.5 rounded transition-colors"
              style={{
                fontSize: 12, fontWeight: tab === "review" ? 600 : 400,
                background: tab === "review" ? "var(--color-elevated)" : "transparent",
                color: tab === "review" ? "var(--color-text)" : "var(--color-text-muted)",
                border: `1px solid ${tab === "review" ? "var(--color-border)" : "transparent"}`,
              }}
            >
              Review {pendingCount > 0 && <span style={{
                marginLeft: 4, fontSize: 10,
                background: "var(--color-err)", color: "#fff",
                borderRadius: 8, padding: "1px 5px",
              }}>{pendingCount}</span>}
            </button>
            <button
              onClick={() => setTab("submit")}
              className="px-3 py-1.5 rounded transition-colors"
              style={{
                fontSize: 12, fontWeight: 600,
                background: tab === "submit" ? "var(--color-lime)" : "transparent",
                color: tab === "submit" ? "#000" : "var(--color-lime)",
                border: `1px solid ${tab === "submit" ? "transparent" : "color-mix(in srgb, var(--color-lime) 35%, transparent)"}`,
              }}
            >
              + Submit
            </button>
          </div>
        }
      />

      {tab === "review" && children.review}
      {tab === "submit" && children.submit}
    </div>
  )
}
