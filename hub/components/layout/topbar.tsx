"use client"

import { signOut } from "next-auth/react"
import { LogOut, Bell } from "lucide-react"
import type { Session } from "next-auth"

interface TopbarProps {
  session: Session
}

export function Topbar({ session }: TopbarProps) {
  return (
    <header
      className="fixed top-0 right-0 flex items-center justify-end gap-3 px-4"
      style={{
        left: "var(--spacing-sidebar)",
        height: "var(--spacing-topbar)",
        background: "var(--color-base)",
        borderBottom: "1px solid var(--color-border)",
        zIndex: 30,
      }}
    >
      {/* Notifications */}
      <button
        className="p-1.5 rounded transition-colors hover:bg-[--color-elevated]"
        style={{ color: "var(--color-text-muted)" }}
        aria-label="Notifications"
      >
        <Bell size={14} />
      </button>

      {/* User */}
      <div className="flex items-center gap-2">
        {session.user?.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={session.user.image}
            alt={session.user.name ?? "User"}
            className="rounded-full"
            style={{ width: 24, height: 24 }}
          />
        ) : (
          <div
            className="rounded-full flex items-center justify-center font-semibold"
            style={{
              width: 24,
              height: 24,
              background: "var(--color-elevated)",
              color: "var(--color-text-muted)",
              fontSize: 10,
            }}
          >
            {session.user?.name?.charAt(0).toUpperCase() ?? "?"}
          </div>
        )}
        <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
          {session.user?.name ?? session.user?.email}
        </span>
      </div>

      {/* Sign out */}
      <button
        onClick={() => signOut({ callbackUrl: "/login" })}
        className="p-1.5 rounded transition-colors hover:bg-[--color-elevated]"
        style={{ color: "var(--color-text-muted)" }}
        aria-label="Sign out"
      >
        <LogOut size={13} />
      </button>
    </header>
  )
}
