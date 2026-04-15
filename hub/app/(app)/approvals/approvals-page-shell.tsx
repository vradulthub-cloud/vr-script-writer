"use client"

import { useState } from "react"

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
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1>
            {tab === "review" ? "Approvals" : "Submit for Approval"}
          </h1>
          {tab === "review" && pendingCount > 0 && (
            <p data-subtitle>{pendingCount} pending decision{pendingCount !== 1 ? "s" : ""}</p>
          )}
        </div>

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
      </div>

      {tab === "review" && children.review}
      {tab === "submit" && children.submit}
    </div>
  )
}
