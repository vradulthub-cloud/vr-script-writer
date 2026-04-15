"use client"

import { useState } from "react"

interface TicketsPageShellProps {
  isAdmin: boolean
  children: {
    tickets: React.ReactNode
    users: React.ReactNode | null
  }
}

export function TicketsPageShell({ isAdmin, children }: TicketsPageShellProps) {
  const [activeTab, setActiveTab] = useState<"tickets" | "users">("tickets")

  const tabs = [
    { key: "tickets" as const, label: "Tickets" },
    ...(isAdmin ? [{ key: "users" as const, label: "Users" }] : []),
  ]

  return (
    <div>
      {/* Page header with tab toggle */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1>
            {activeTab === "tickets" ? "Tickets" : "User Management"}
          </h1>
        </div>

        {/* Sub-tab toggle (only show if admin) */}
        {isAdmin && (
          <div
            className="flex rounded overflow-hidden"
            style={{ border: "1px solid var(--color-border)" }}
          >
            {tabs.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className="px-3 py-1.5 transition-colors"
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  background: activeTab === key ? "var(--color-elevated)" : "transparent",
                  color: activeTab === key ? "var(--color-text)" : "var(--color-text-muted)",
                  borderRight: key !== tabs[tabs.length - 1].key ? "1px solid var(--color-border)" : undefined,
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      {activeTab === "tickets" && children.tickets}
      {activeTab === "users" && children.users}
    </div>
  )
}
