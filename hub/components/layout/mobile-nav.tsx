"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutGrid,
  FileText,
  Image,
  AlignLeft,
  Ticket,
} from "lucide-react"

const MOBILE_ITEMS = [
  { href: "/missing",      label: "Missing",  icon: LayoutGrid },
  { href: "/scripts",      label: "Scripts",   icon: FileText },
  { href: "/titles",       label: "Titles",    icon: Image },
  { href: "/descriptions", label: "Desc",      icon: AlignLeft },
  { href: "/tickets",      label: "Tickets",   icon: Ticket },
]

export function MobileNav() {
  const pathname = usePathname()

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 flex items-center justify-around md:hidden"
      style={{
        height: 56,
        background: "var(--color-surface)",
        borderTop: "1px solid var(--color-border)",
        zIndex: 50,
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      {MOBILE_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname.startsWith(href)
        return (
          <Link
            key={href}
            href={href}
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
      })}
    </nav>
  )
}
