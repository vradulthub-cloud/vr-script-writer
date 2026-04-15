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
  { href: "/tickets",      label: "Tickets",        icon: Ticket },
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
        className="flex items-center gap-2 px-4 shrink-0"
        style={{
          height: "var(--spacing-topbar)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <span
          className="font-bold tracking-tight"
          style={{ fontSize: 14, color: "var(--color-lime)" }}
        >
          ECLATECH
        </span>
        <span style={{ fontSize: 14, color: "var(--color-text-muted)" }}>
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
              className={cn(
                "flex items-center gap-2.5 px-4 py-2 transition-colors",
                "text-sm leading-none",
                active
                  ? "font-medium"
                  : "hover:bg-[--color-elevated]"
              )}
              style={{
                color: active ? "var(--color-text)" : "var(--color-text-muted)",
                background: active ? "var(--color-elevated)" : undefined,
                borderLeft: active
                  ? "2px solid var(--color-lime)"
                  : "2px solid transparent",
              }}
            >
              <Icon
                size={14}
                style={{ color: active ? "var(--color-lime)" : undefined }}
              />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom: version */}
      <div
        className="px-4 py-3 shrink-0"
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
