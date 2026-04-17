"use client"

import { useState, useEffect, useRef, useMemo } from "react"
import { useRouter, usePathname } from "next/navigation"
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
  Search,
} from "lucide-react"

const COMMANDS = [
  { id: "missing",      label: "Asset Tracker",    href: "/missing",      icon: LayoutGrid,  shortcut: "1" },
  { id: "research",     label: "Model Research",    href: "/research",     icon: Users,        shortcut: "2" },
  { id: "scripts",      label: "Scripts",           href: "/scripts",      icon: FileText,     shortcut: "3" },
  { id: "call-sheets",  label: "Call Sheets",       href: "/call-sheets",  icon: Phone,        shortcut: "4" },
  { id: "titles",       label: "Titles",            href: "/titles",       icon: Image,        shortcut: "5" },
  { id: "descriptions", label: "Descriptions",      href: "/descriptions", icon: AlignLeft,    shortcut: "6" },
  { id: "compilations", label: "Compilations",      href: "/compilations", icon: Layers,       shortcut: "7" },
  { id: "approvals",    label: "Approvals",         href: "/approvals",    icon: CheckSquare,  shortcut: "8" },
  { id: "tickets",      label: "Tickets",           href: "/tickets",      icon: Ticket,       shortcut: "9" },
  { id: "admin",        label: "Admin",             href: "/admin",        icon: Users,        shortcut: "0" },
]

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const pathname = usePathname()

  // Open on Cmd+K (or ?) + Cmd+1-9 for direct nav + custom event for mouse trigger
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setOpen(v => !v)
        setQuery("")
        setSelectedIdx(0)
      }
      // ? opens the palette (palette footer lists all shortcuts)
      if (e.key === "?" && !isInputFocused(e) && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault()
        setOpen(true)
        setQuery("")
        setSelectedIdx(0)
      }
      // Cmd+1-9 for direct nav
      if ((e.metaKey || e.ctrlKey) && e.key >= "1" && e.key <= "9") {
        const cmd = COMMANDS[parseInt(e.key) - 1]
        if (cmd && !isInputFocused(e)) {
          e.preventDefault()
          router.push(cmd.href)
        }
      }
    }
    function onOpenEvent() {
      setOpen(true)
      setQuery("")
      setSelectedIdx(0)
    }
    window.addEventListener("keydown", onKeyDown)
    window.addEventListener("hub:open-palette", onOpenEvent as EventListener)
    return () => {
      window.removeEventListener("keydown", onKeyDown)
      window.removeEventListener("hub:open-palette", onOpenEvent as EventListener)
    }
  }, [router])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  const filtered = useMemo(() => {
    if (!query) return COMMANDS
    const q = query.toLowerCase()
    return COMMANDS.filter(c =>
      c.label.toLowerCase().includes(q) || c.id.includes(q)
    )
  }, [query])

  // Reset selection when filtered list changes
  useEffect(() => {
    setSelectedIdx(0)
  }, [filtered.length])

  function navigate(href: string) {
    setOpen(false)
    setQuery("")
    router.push(href)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setSelectedIdx(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setSelectedIdx(i => Math.max(i - 1, 0))
    } else if (e.key === "Enter" && filtered[selectedIdx]) {
      e.preventDefault()
      navigate(filtered[selectedIdx].href)
    } else if (e.key === "Escape") {
      setOpen(false)
    }
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0"
        style={{ background: "rgba(0,0,0,0.5)", zIndex: 200 }}
        onClick={() => setOpen(false)}
      />

      {/* Palette */}
      <div
        className="fixed overflow-hidden"
        style={{
          top: "min(20%, 160px)",
          left: "50%",
          transform: "translateX(-50%)",
          width: "min(480px, 90vw)",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          zIndex: 201,
          animation: "dropdownIn 150ms var(--ease-out-expo) both",
          boxShadow: "0 16px 48px rgba(0,0,0,0.5)",
        }}
      >
        {/* Input */}
        <div className="flex items-center gap-2 px-3" style={{ borderBottom: "1px solid var(--color-border)" }}>
          <Search size={14} style={{ color: "var(--color-text-faint)", flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Navigate to..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 py-2.5 bg-transparent outline-none"
            style={{
              fontSize: 13,
              color: "var(--color-text)",
              border: "none",
              boxShadow: "none",
            }}
          />
          <kbd
            style={{
              fontSize: 10,
              color: "var(--color-text-faint)",
              background: "var(--color-elevated)",
              padding: "2px 5px",
              borderRadius: 4,
              fontFamily: "var(--font-mono)",
            }}
          >
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="py-1" style={{ maxHeight: 320, overflowY: "auto" }}>
          {filtered.length === 0 && (
            <div className="px-3 py-4 text-center" style={{ fontSize: 12, color: "var(--color-text-faint)" }}>
              No matching pages
            </div>
          )}
          {filtered.map((cmd, i) => {
            const Icon = cmd.icon
            const isActive = pathname.startsWith(cmd.href)
            return (
              <button
                key={cmd.id}
                onClick={() => navigate(cmd.href)}
                className="flex items-center gap-2.5 w-full px-3 py-2 transition-colors text-left"
                style={{
                  fontSize: 13,
                  color: i === selectedIdx ? "var(--color-text)" : "var(--color-text-muted)",
                  background: i === selectedIdx ? "var(--color-elevated)" : "transparent",
                }}
              >
                <Icon size={14} style={{ color: isActive ? "var(--color-lime)" : undefined, flexShrink: 0 }} />
                <span className="flex-1">{cmd.label}</span>
                <kbd
                  style={{
                    fontSize: 10,
                    color: "var(--color-text-faint)",
                    fontFamily: "var(--font-mono)",
                    background: "var(--color-elevated)",
                    padding: "2px 5px",
                    borderRadius: 4,
                  }}
                >
                  ⌘{cmd.shortcut}
                </kbd>
              </button>
            )
          })}
        </div>

        {/* Footer hint */}
        <div
          className="flex items-center gap-3 px-3 py-1.5"
          style={{ borderTop: "1px solid var(--color-border)", fontSize: 10, color: "var(--color-text-faint)" }}
        >
          <span><kbd style={{ fontFamily: "var(--font-mono)" }}>↑↓</kbd> navigate</span>
          <span><kbd style={{ fontFamily: "var(--font-mono)" }}>↵</kbd> open</span>
          <span><kbd style={{ fontFamily: "var(--font-mono)" }}>⌘1–9</kbd> jump</span>
          <span style={{ marginLeft: "auto" }}><kbd style={{ fontFamily: "var(--font-mono)" }}>?</kbd> shortcuts</span>
        </div>
      </div>
    </>
  )
}

/** Check if an input/textarea/select is focused (don't steal shortcuts from form fields) */
function isInputFocused(e: KeyboardEvent): boolean {
  const tag = (e.target as HTMLElement)?.tagName
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
}
