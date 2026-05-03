"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Home,
  LayoutGrid,
  FileText,
  Image,
  AlignLeft,
  Users,
  Phone,
  Layers,
  Ticket,
  ClipboardCheck,
  MoreHorizontal,
} from "lucide-react"

const PRIMARY_ITEMS = [
  { href: "/dashboard", label: "Home",    icon: Home },
  { href: "/shoots",    label: "Shoots",  icon: LayoutGrid },
  { href: "/missing",   label: "Assets",  icon: Layers },
  { href: "/scripts",   label: "Scripts", icon: FileText },
]

const OVERFLOW_ITEMS = [
  { href: "/compliance",   label: "Compliance",   icon: ClipboardCheck },
  { href: "/tickets",      label: "Tickets",      icon: Ticket },
  { href: "/descriptions", label: "Descriptions", icon: AlignLeft },
  { href: "/research",     label: "Research",     icon: Users },
  { href: "/call-sheets",  label: "Calls",        icon: Phone },
  { href: "/compilations", label: "Comps",        icon: Layers },
  { href: "/titles",       label: "Titles",       icon: Image },
]

export function MobileNav() {
  const pathname = usePathname()
  const [moreOpen, setMoreOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Is the current page in the overflow menu?
  const overflowActive = OVERFLOW_ITEMS.some(i => pathname.startsWith(i.href))

  // Close on outside click
  useEffect(() => {
    if (!moreOpen) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMoreOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [moreOpen])

  // Close on navigation
  useEffect(() => { setMoreOpen(false) }, [pathname])

  function NavItem({ href, label, icon: Icon }: { href: string; label: string; icon: typeof LayoutGrid }) {
    const active = pathname.startsWith(href)
    return (
      <Link
        href={href}
        prefetch={false}
        className="flex flex-col items-center justify-center gap-0.5"
        style={{
          flex: 1,
          color: active ? "var(--color-lime)" : "var(--color-text-faint)",
          fontSize: 9,
          fontWeight: active ? 600 : 400,
          textDecoration: "none",
          paddingTop: 6,
          paddingBottom: 2,
        }}
      >
        <Icon size={18} />
        {label}
      </Link>
    )
  }

  return (
    <div className="md:hidden" ref={menuRef}>
      {/* Overflow menu */}
      {moreOpen && (
        <div
          className="fixed bottom-14 right-2 rounded-lg overflow-hidden"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            boxShadow: "0 -4px 24px rgba(0,0,0,0.4)",
            zIndex: 51,
            animation: "dropdownIn 150ms var(--ease-out-expo) both",
            minWidth: 160,
          }}
        >
          {OVERFLOW_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                prefetch={false}
                className="flex items-center gap-2.5 px-3 py-2.5 transition-colors"
                style={{
                  fontSize: 12,
                  color: active ? "var(--color-lime)" : "var(--color-text-muted)",
                  background: active ? "color-mix(in srgb, var(--color-lime) 8%, transparent)" : undefined,
                  borderBottom: "1px solid var(--color-border-subtle)",
                  textDecoration: "none",
                }}
              >
                <Icon size={14} />
                {label}
              </Link>
            )
          })}
        </div>
      )}

      {/* Bottom nav bar */}
      <nav
        className="fixed bottom-0 left-0 right-0 flex items-center justify-around"
        style={{
          height: 56,
          background: "var(--color-surface)",
          borderTop: "1px solid var(--color-border)",
          zIndex: 50,
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        {PRIMARY_ITEMS.map((item) => (
          <NavItem key={item.href} {...item} />
        ))}

        {/* More button */}
        <button
          type="button"
          onClick={() => setMoreOpen(v => !v)}
          className="flex flex-col items-center justify-center gap-0.5"
          style={{
            flex: 1,
            color: moreOpen || overflowActive ? "var(--color-lime)" : "var(--color-text-faint)",
            fontSize: 9,
            fontWeight: moreOpen || overflowActive ? 600 : 400,
            paddingTop: 6,
            paddingBottom: 2,
            background: "transparent",
            border: "none",
          }}
        >
          <MoreHorizontal size={18} />
          More
        </button>
      </nav>
    </div>
  )
}
