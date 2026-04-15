"use client"

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

const NAV_ITEMS = [
  { href: "/missing",      label: "Missing",       icon: LayoutGrid },
  { href: "/research",     label: "Model Research", icon: Users },
  { href: "/scripts",      label: "Scripts",        icon: FileText },
  { href: "/call-sheets",  label: "Call Sheets",    icon: Phone },
  { href: "/titles",       label: "Titles",         icon: Image },
  { href: "/descriptions", label: "Descriptions",   icon: AlignLeft },
  { href: "/compilations", label: "Compilations",   icon: Layers },
  { href: "/approvals",   label: "Approvals",       icon: CheckSquare },
  { href: "/tickets",     label: "Tickets",         icon: Ticket },
] as const

export function Sidebar() {
  const pathname = usePathname()

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
        <span
          className="font-bold tracking-tight"
          style={{ fontSize: 14, color: "var(--color-lime)" }}
        >
          {/* Icon-only: show single "E" glyph; expanded: full wordmark */}
          <span className="xl:hidden">E</span>
          <span className="hidden xl:inline">ECLATECH</span>
        </span>
        <span className="hidden xl:inline" style={{ fontSize: 14, color: "var(--color-text-muted)" }}>
          HUB
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className={cn(
                "flex items-center gap-2.5 py-2 transition-colors",
                "justify-center px-0 xl:justify-start xl:px-4",
                "text-sm leading-none",
                active
                  ? "font-medium"
                  : "hover:bg-[--color-elevated]"
              )}
              style={{
                color: active ? "var(--color-text)" : "var(--color-text-muted)",
                background: active ? "var(--color-elevated)" : undefined,
              }}
            >
              <Icon
                size={14}
                style={{ color: active ? "var(--color-lime)" : undefined }}
              />
              <span className="hidden xl:inline">{label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Bottom: version — hidden at icon-only width */}
      <div
        className="hidden xl:block px-4 py-3 shrink-0"
        style={{
          borderTop: "1px solid var(--color-border)",
          color: "var(--color-text-faint)",
          fontSize: 11,
        }}
      >
        v2.0 — Next.js
      </div>
    </aside>
  )
}
