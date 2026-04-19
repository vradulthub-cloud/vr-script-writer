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
          <div className="flex rounded overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
            {(["review", "submit"] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className="px-3 py-1.5 transition-colors capitalize"
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  background: tab === t ? "var(--color-elevated)" : "transparent",
                  color: tab === t ? "var(--color-text)" : "var(--color-text-muted)",
                  borderRight: t === "review" ? "1px solid var(--color-border)" : undefined,
                }}
              >
                {t === "review" ? "Review" : "Submit"}
              </button>
            ))}
          </div>
        }
      />

      {tab === "review" && children.review}
      {tab === "submit" && children.submit}
    </div>
  )
}
