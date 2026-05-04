"use client"

import { useMemo, useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  AlertCircle,
  Calendar,
  Users,
  FileText,
  CalendarDays,
  ImageIcon,
  AlignLeft,
  Layers,
  Ticket,
  Shield,
  ClipboardCheck,
  UploadCloud,
} from "lucide-react"
import { cn } from "@/lib/utils"

// ─── Nav structure ────────────────────────────────────────────────────────────

const CORE_ITEMS = [
  { href: "/dashboard", label: "Dashboard", shortLabel: "Home", icon: LayoutDashboard },
] as const

const NAV_SECTIONS = [
  {
    label: "Production",
    items: [
      { href: "/shoots",      label: "Shoot Tracker",  shortLabel: "Shoots",   icon: Calendar,         tabKey: "Shoots" },
      { href: "/compliance",  label: "Compliance",     shortLabel: "Legal",    icon: ClipboardCheck,   tabKey: "Shoots" },
      { href: "/call-sheets", label: "Call Sheets",    shortLabel: "Calls",    icon: CalendarDays,     tabKey: "Call Sheets" },
      { href: "/research",    label: "Model Research", shortLabel: "Research", icon: Users,            tabKey: "Model Research" },
    ],
  },
  {
    label: "Writing Room",
    items: [
      { href: "/scripts",      label: "Scripts",       shortLabel: "Scripts", icon: FileText, tabKey: "Scripts" },
      { href: "/descriptions", label: "Descriptions",  shortLabel: "Descs",   icon: AlignLeft, tabKey: "Descriptions" },
      { href: "/compilations", label: "Compilations",  shortLabel: "Comps",   icon: Layers,    tabKey: "Compilations" },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/missing", label: "Grail Assets", shortLabel: "Grail",   icon: AlertCircle, tabKey: "Tickets" },
      { href: "/uploads", label: "Uploads",      shortLabel: "Upload",  icon: UploadCloud },
      { href: "/titles",  label: "Titles",       shortLabel: "Titles",  icon: ImageIcon,   tabKey: "Titles" },
      { href: "/tickets", label: "Tickets",      shortLabel: "Tickets", icon: Ticket,      tabKey: "Tickets" },
    ],
  },
] as const

interface SidebarProps {
  allowedTabs: string   // comma-separated tab keys or "ALL"
  userRole: string      // "admin" | "editor"
}

export function Sidebar({ allowedTabs, userRole }: SidebarProps) {
  const pathname = usePathname()

  const allowed = useMemo(() => {
    if (userRole === "admin" || allowedTabs === "ALL") return null // null = all
    return new Set(allowedTabs.split(",").map(t => t.trim()).filter(Boolean))
  }, [allowedTabs, userRole])

  function NavLink({
    href,
    label,
    shortLabel,
    icon: Icon,
  }: {
    href: string
    label: string
    shortLabel: string
    icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>
  }) {
    const active = href === "/dashboard" ? pathname === href : pathname.startsWith(href)
    return (
      <Link
        href={href}
        title={label}
        prefetch={false}
        data-active={active || undefined}
        className={cn(
          "flex items-center gap-2.5 py-1.5 transition-colors",
          "flex-col gap-0.5 lg:flex-col lg:justify-center lg:px-0",
          "xl:flex-row xl:justify-start xl:gap-2.5",
          "text-sm leading-none",
          active
            ? "font-medium bg-[--color-elevated] xl:border-l-2 xl:border-[--color-lime] xl:pl-[14px]"
            : "hover:bg-[--color-elevated] xl:pl-4",
        )}
        style={{ color: active ? "var(--color-text)" : "var(--color-text-muted)" }}
      >
        <Icon size={13} style={{ color: active ? "var(--color-lime)" : undefined, flexShrink: 0 }} />
        <span className="hidden xl:inline">{label}</span>
        <span
          className="hidden lg:block xl:hidden text-center leading-none"
          style={{ fontSize: 8, letterSpacing: "0.02em", opacity: 0.85 }}
        >
          {shortLabel}
        </span>
      </Link>
    )
  }

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
      {/* Wordmark */}
      <Link
        href="/dashboard"
        aria-label="Eclatech Hub — Dashboard"
        prefetch={false}
        className="flex items-center justify-center xl:justify-start gap-2 px-0 xl:px-4 shrink-0 transition-opacity hover:opacity-80"
        style={{
          height: "var(--spacing-topbar)",
          borderBottom: "1px solid var(--color-border)",
          textDecoration: "none",
        }}
      >
        <span className="xl:hidden font-bold" style={{ fontSize: 15, color: "var(--color-lime)", letterSpacing: "0.08em" }}>E</span>
        <span className="hidden xl:inline-flex items-center gap-2">
          <span aria-hidden="true" style={{ display: "inline-block", width: 1, height: 16, background: "var(--color-lime)", opacity: 0.4 }} />
          <span className="font-bold" style={{ fontSize: 15, color: "var(--color-lime)", letterSpacing: "0.08em" }}>ECLATECH</span>
          <span aria-hidden="true" style={{ display: "inline-block", width: 1, height: 16, background: "var(--color-lime)", opacity: 0.4 }} />
        </span>
        <span className="hidden xl:inline" style={{ fontSize: 13, color: "var(--color-text-faint)", fontWeight: 400, letterSpacing: "0.12em" }}>
          HUB
        </span>
      </Link>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2" aria-label="Main navigation">

        {/* Core items — Dashboard + Missing — always visible */}
        {CORE_ITEMS.map(item => (
          <NavLink key={item.href} {...item} />
        ))}

        {/* Sectioned nav */}
        {NAV_SECTIONS.map(section => {
          const visible = section.items.filter(
            // No tabKey = visible to everyone (e.g. Uploads, intentionally
            // ungated). Otherwise: admins always see it; editors only if
            // their allowed_tabs include the key.
            item => !("tabKey" in item) || allowed === null || allowed.has((item as { tabKey: string }).tabKey),
          )
          if (visible.length === 0) return null
          return (
            <div key={section.label}>
              {/* Section label — only visible at xl+ (collapsed rail has no room) */}
              <div
                className="hidden xl:block"
                style={{
                  padding: "14px 16px 4px",
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  color: "var(--color-text-muted)",
                  userSelect: "none",
                }}
              >
                {section.label}
              </div>
              {/* Divider only in collapsed rail */}
              <div
                className="block xl:hidden"
                style={{ height: 1, background: "var(--color-border)", margin: "6px 12px" }}
              />
              {visible.map(item => (
                <NavLink key={item.href} {...item} />
              ))}
            </div>
          )
        })}

        {/* Admin — separated, admin-only */}
        {userRole === "admin" && (
          <>
            <div style={{ height: 1, background: "var(--color-border)", margin: "6px 12px" }} />
            <NavLink href="/admin" label="Admin" shortLabel="Admin" icon={Shield} />
          </>
        )}
      </nav>

      <RailClock />
    </aside>
  )
}

function RailClock() {
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    setNow(new Date())
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  if (!now) return <div style={{ height: 64, borderTop: "1px solid var(--color-border)" }} />

  const p = (n: number) => String(n).padStart(2, "0")
  const h24 = now.getHours()
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12
  const ampm = h24 < 12 ? "AM" : "PM"
  const time = `${h12}:${p(now.getMinutes())}:${p(now.getSeconds())} ${ampm}`
  const timeShort = `${h12}:${p(now.getMinutes())} ${ampm}`
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone.split("/").pop()?.replace("_", " ") ?? "LOCAL"
  const dayDate = now
    .toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
    .toUpperCase()
    .replace(",", " ·")

  return (
    <div
      style={{
        borderTop: "1px solid var(--color-border)",
        padding: "10px 0 12px",
        textAlign: "center",
        flexShrink: 0,
        userSelect: "none",
      }}
    >
      {/* Collapsed rail: just HH:MM */}
      <div
        className="block xl:hidden"
        style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-text-faint)", letterSpacing: "0.06em" }}
      >
        {timeShort}
      </div>

      {/* Expanded: full clock block */}
      <div className="hidden xl:flex flex-col items-center gap-1">
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 20,
            fontWeight: 600,
            letterSpacing: "0.08em",
            color: "var(--color-text-muted)",
            lineHeight: 1,
          }}
        >
          {time}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            padding: "0 14px",
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
            marginTop: 3,
          }}
        >
          <span>{dayDate}</span>
          <span style={{ opacity: 0.7 }}>{tz}</span>
        </div>
      </div>
    </div>
  )
}
