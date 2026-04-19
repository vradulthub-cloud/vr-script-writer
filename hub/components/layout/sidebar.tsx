"use client"

import { useMemo } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Home,
  LayoutGrid,
  Users,
  FileText,
  Phone,
  Image,
  AlignLeft,
  Layers,
  Ticket,
  CheckSquare,
  Shield,
  Calendar,
} from "lucide-react"
import { cn } from "@/lib/utils"

/** Always-visible items — shown for every user regardless of RBAC. */
const CORE_ITEMS = [
  { href: "/dashboard", label: "Dashboard", shortLabel: "Home", icon: Home },
] as const

/**
 * Map from nav label → the key used in the users.allowed_tabs column.
 * The Streamlit app's auth_config ALL_TABS uses these exact keys.
 */
const NAV_ITEMS = [
  { href: "/shoots",       label: "Shoot Tracker",  shortLabel: "Shoots",   tabKey: "Shoots",         icon: Calendar },
  { href: "/missing",      label: "Studio Catalog",  shortLabel: "Scenes",   tabKey: "Tickets",        icon: LayoutGrid },
  { href: "/research",     label: "Model Research", shortLabel: "Research", tabKey: "Model Research", icon: Users },
  { href: "/scripts",      label: "Scripts",         shortLabel: "Scripts",  tabKey: "Scripts",        icon: FileText },
  { href: "/call-sheets",  label: "Call Sheets",     shortLabel: "Calls",    tabKey: "Call Sheets",    icon: Phone },
  { href: "/titles",       label: "Titles",           shortLabel: "Titles",   tabKey: "Titles",         icon: Image },
  { href: "/descriptions", label: "Descriptions",   shortLabel: "Descs",    tabKey: "Descriptions",   icon: AlignLeft },
  { href: "/compilations", label: "Compilations",   shortLabel: "Comps",    tabKey: "Compilations",   icon: Layers },
  { href: "/approvals",    label: "Approvals",       shortLabel: "Approve",  tabKey: "Tickets",        icon: CheckSquare },
  { href: "/tickets",      label: "Tickets",          shortLabel: "Tickets",  tabKey: "Tickets",        icon: Ticket },
] as const

interface SidebarProps {
  allowedTabs: string   // comma-separated tab keys or "ALL"
  userRole: string      // "admin" | "editor"
}

export function Sidebar({ allowedTabs, userRole }: SidebarProps) {
  const pathname = usePathname()

  const visibleItems = useMemo(() => {
    // Admins always see everything. Everyone else is gated by allowed_tabs.
    // Empty allowed_tabs === no access: showing all would silently grant
    // access to a user whose permissions haven't been set up.
    if (userRole === "admin" || allowedTabs === "ALL") {
      return NAV_ITEMS
    }
    const allowed = new Set(
      allowedTabs.split(",").map((t) => t.trim()).filter(Boolean),
    )
    return NAV_ITEMS.filter((item) => allowed.has(item.tabKey))
  }, [allowedTabs, userRole])

  return (
    <aside
      className="fixed top-0 left-0 h-full flex flex-col"
      style={{
        width: "var(--spacing-sidebar)",
        background: "var(--color-surface)",
        borderRight: "1px solid var(--color-border)",
        zIndex: 40,
      }}
    >
      {/* Logo — links home, per convention */}
      <Link
        href="/dashboard"
        aria-label="Eclatech Hub — Dashboard"
        className="flex items-center justify-center xl:justify-start gap-2 px-0 xl:px-4 shrink-0 transition-opacity hover:opacity-80"
        style={{
          height: "var(--spacing-topbar)",
          borderBottom: "1px solid var(--color-border)",
          textDecoration: "none",
        }}
      >
        {/* Collapsed: single letter */}
        <span className="xl:hidden font-bold" style={{ fontSize: 15, color: "var(--color-lime)", letterSpacing: "0.08em" }}>E</span>

        {/* Full wordmark with film-frame flanking rules */}
        <span className="hidden xl:inline-flex items-center gap-2">
          {/* Left perforation */}
          <span aria-hidden="true" style={{ display: "inline-block", width: 1, height: 16, background: "var(--color-lime)", opacity: 0.4 }} />
          <span className="font-bold" style={{ fontSize: 15, color: "var(--color-lime)", letterSpacing: "0.08em" }}>ECLATECH</span>
          {/* Right perforation */}
          <span aria-hidden="true" style={{ display: "inline-block", width: 1, height: 16, background: "var(--color-lime)", opacity: 0.4 }} />
        </span>

        <span className="hidden xl:inline" style={{ fontSize: 13, color: "var(--color-text-faint)", fontWeight: 400, letterSpacing: "0.12em" }}>
          HUB
        </span>
      </Link>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        {/* Core items — always visible */}
        {CORE_ITEMS.map(({ href, label, shortLabel, icon: Icon }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              title={label}
              data-active={active || undefined}
              className={cn(
                "flex items-center gap-2.5 py-2 transition-colors",
                "flex-col gap-0.5 lg:flex-col lg:justify-center lg:px-0",
                "xl:flex-row xl:justify-start xl:px-4 xl:gap-2.5",
                "text-sm leading-none",
                active
                  ? "font-medium"
                  : "hover:bg-[--color-elevated]"
              )}
              style={{
                color: active ? "var(--color-text)" : "var(--color-text-muted)",
              }}
            >
              <Icon
                size={14}
                style={{ color: active ? "var(--color-lime)" : undefined }}
              />
              <span className="hidden xl:inline">{label}</span>
              <span
                className="hidden lg:block xl:hidden text-center leading-none"
                style={{ fontSize: 8, letterSpacing: "0.02em", opacity: 0.85 }}
              >
                {shortLabel}
              </span>
            </Link>
          )
        })}

        {/* Divider between core and RBAC-filtered items */}
        <div style={{ height: 1, background: "var(--color-border)", margin: "6px 12px" }} />

        {visibleItems.map(({ href, label, shortLabel, icon: Icon }) => {
          const active = pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              title={label}
              data-active={active || undefined}
              className={cn(
                "flex items-center gap-2.5 py-2 transition-colors",
                // lg: stacked icon+label in 52px rail; xl: horizontal with full label
                "flex-col gap-0.5 lg:flex-col lg:justify-center lg:px-0",
                "xl:flex-row xl:justify-start xl:px-4 xl:gap-2.5",
                "text-sm leading-none",
                active
                  ? "font-medium"
                  : "hover:bg-[--color-elevated]"
              )}
              style={{
                color: active ? "var(--color-text)" : "var(--color-text-muted)",
              }}
            >
              <Icon
                size={14}
                style={{ color: active ? "var(--color-lime)" : undefined }}
              />
              {/* Full label at xl+ */}
              <span className="hidden xl:inline">{label}</span>
              {/* Short label at lg–xl (52px rail) */}
              <span
                className="hidden lg:block xl:hidden text-center leading-none"
                style={{ fontSize: 8, letterSpacing: "0.02em", opacity: 0.85 }}
              >
                {shortLabel}
              </span>
            </Link>
          )
        })}

        {/* Admin — separated, admin-only */}
        {userRole === "admin" && (
          <>
            <div style={{ height: 1, background: "var(--color-border)", margin: "6px 12px" }} />
            {(() => {
              const active = pathname.startsWith("/admin")
              return (
                <Link
                  href="/admin"
                  title="Admin"
                  data-active={active || undefined}
                  className={cn(
                    "flex items-center gap-2.5 py-2 transition-colors",
                    "flex-col gap-0.5 lg:flex-col lg:justify-center lg:px-0",
                    "xl:flex-row xl:justify-start xl:px-4 xl:gap-2.5",
                    "text-sm leading-none",
                    active ? "font-medium" : "hover:bg-[--color-elevated]"
                  )}
                  style={{ color: active ? "var(--color-text)" : "var(--color-text-muted)" }}
                >
                  <Shield size={14} style={{ color: active ? "var(--color-lime)" : undefined }} />
                  <span className="hidden xl:inline">Admin</span>
                  <span className="hidden lg:block xl:hidden text-center leading-none" style={{ fontSize: 8, letterSpacing: "0.02em", opacity: 0.85 }}>
                    Admin
                  </span>
                </Link>
              )
            })()}
          </>
        )}
      </nav>

    </aside>
  )
}
