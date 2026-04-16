"use client"

import { useMemo } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutGrid,
  Users,
  FileText,
  Phone,
  Image,
  AlignLeft,
  Layers,
  Ticket,
  CheckSquare,
} from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Map from nav label → the key used in the users.allowed_tabs column.
 * The Streamlit app's auth_config ALL_TABS uses these exact keys.
 */
const NAV_ITEMS = [
  { href: "/missing",      label: "Missing",       shortLabel: "Missing",  tabKey: "Tickets",        icon: LayoutGrid },
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
    // Admins see everything
    if (userRole === "admin" || allowedTabs === "ALL" || !allowedTabs) {
      return NAV_ITEMS
    }
    const allowed = new Set(
      allowedTabs.split(",").map((t) => t.trim())
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
      {/* Logo */}
      <div
        className="flex items-center justify-center xl:justify-start gap-2 px-0 xl:px-4 shrink-0"
        style={{
          height: "var(--spacing-topbar)",
          borderBottom: "1px solid var(--color-border)",
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
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
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
      </nav>

      {/* Bottom: version */}
      <div
        className="hidden xl:block px-4 py-3 shrink-0"
        style={{
          borderTop: "1px solid var(--color-border)",
          color: "var(--color-text-faint)",
          fontSize: 11,
        }}
      >
        Eclatech Hub
      </div>
    </aside>
  )
}
