"use client"

import { usePathname } from "next/navigation"
import { signOut } from "next-auth/react"
import { LogOut } from "lucide-react"
import type { Session } from "next-auth"
import { NotificationBell } from "./notification-bell"
import { HelpButton } from "@/components/ui/help-modal"

const PAGE_NAMES: Record<string, string> = {
  "/dashboard":    "Dashboard",
  "/shoots":       "Shoot Tracker",
  "/missing":      "Grail Assets",
  "/research":     "Model Research",
  "/scripts":      "Scripts",
  "/call-sheets":  "Call Sheets",
  "/titles":       "Titles",
  "/descriptions": "Descriptions",
  "/compilations": "Compilations",
  "/tickets":      "Tickets",
}

interface TopbarProps {
  session: Session
  idToken: string | undefined
  userRole: string
}

export function Topbar({ session, idToken, userRole }: TopbarProps) {
  const pathname = usePathname()
  const pageName = Object.entries(PAGE_NAMES).find(([key]) => pathname.startsWith(key))?.[1]

  return (
    <header
      className="fixed top-0 right-0 flex items-center gap-3 px-4"
      style={{
        left: "var(--spacing-sidebar)",
        height: "var(--spacing-topbar)",
        background: "var(--color-base)",
        borderBottom: "1px solid var(--color-border)",
        zIndex: 30,
      }}
    >
      {/* Mobile page title — visible only when sidebar is hidden */}
      {pageName && (
        <span
          className="md:hidden font-semibold"
          style={{ fontSize: 13, color: "var(--color-text)" }}
        >
          {pageName}
        </span>
      )}

      {/* Desktop page title — lightweight orientation label */}
      {pageName && (
        <span
          className="hidden md:block"
          style={{ fontSize: 12, color: "var(--color-text-muted)", letterSpacing: "0.01em" }}
        >
          {pageName}
        </span>
      )}

      {/* Right-side controls — ml-auto pushes to far right */}
      <div className="ml-auto flex items-center gap-3">
        <button
          onClick={() => window.dispatchEvent(new CustomEvent("hub:open-palette"))}
          title="Open command palette (⌘K)"
          aria-label="Open command palette"
          className="hidden sm:flex items-center gap-1.5 rounded transition-colors hover:bg-[--color-elevated]"
          style={{
            padding: "3px 8px",
            border: "1px solid var(--color-border)",
            background: "transparent",
            color: "var(--color-text-faint)",
            cursor: "pointer",
          }}
        >
          <span style={{ fontSize: 11 }}>Jump to…</span>
          <kbd
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--color-text-faint)",
              background: "var(--color-elevated)",
              padding: "1px 4px",
              borderRadius: 3,
            }}
          >
            ⌘K
          </kbd>
        </button>

        <HelpButton />

        <NotificationBell idToken={idToken} />

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
          {/* Hide username text on mobile to save space */}
          <span className="hidden md:inline" style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
            {session.user?.name ?? session.user?.email}
          </span>
        </div>

        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="p-1.5 rounded transition-colors hover:bg-[--color-elevated]"
          style={{ color: "var(--color-text-muted)" }}
          aria-label="Sign out"
        >
          <LogOut size={13} />
        </button>
      </div>
    </header>
  )
}
