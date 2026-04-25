"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Bell, Check, Ticket } from "lucide-react"
import type { Notification } from "@/lib/api"
import { API_BASE_URL } from "@/lib/api"
import { showToast } from "@/components/ui/toast"

// Approval icons + the /approvals link mapping were removed when the team
// paused the approvals workflow. If a legacy notification with link "Approvals"
// arrives, it falls through to "#" rather than navigating to a dead route.
const TYPE_ICON: Record<string, React.ComponentType<{ size?: number; style?: React.CSSProperties }>> = {
  ticket_created: Ticket,
  ticket_status:  Ticket,
}

// Legacy rows wrote bare tab names ("Tickets"); map to real routes.
function normalizeNotifLink(link: string | null | undefined): string {
  if (!link) return "#"
  if (link.startsWith("/")) return link
  const map: Record<string, string> = {
    Tickets: "/tickets",
    Scripts: "/scripts",
    Missing: "/missing",
    "Model Research": "/research",
    "Call Sheets": "/call-sheets",
    Titles: "/titles",
    Descriptions: "/descriptions",
    Compilations: "/compilations",
    Shoots: "/shoots",
  }
  return map[link] ?? "#"
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 2)  return "just now"
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

interface NotificationFeedProps {
  initialNotifications: Notification[]
  idToken: string | undefined
  unreadCount: number
}

export function NotificationFeed({
  initialNotifications,
  idToken,
  unreadCount: initialUnread,
}: NotificationFeedProps) {
  const [notifications, setNotifications] = useState(initialNotifications)
  const [unreadCount, setUnreadCount]     = useState(initialUnread)
  const [marking, setMarking]             = useState(false)

  useEffect(() => {
    if (!idToken) return

    async function fetchNotifications() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/notifications/?limit=12`, {
          headers: { Authorization: `Bearer ${idToken!}` },
        })
        if (res.ok) {
          const data: Notification[] = await res.json()
          setNotifications(data)
          setUnreadCount(data.filter(n => n.read === 0).length)
        }
      } catch {}
    }

    const interval = setInterval(fetchNotifications, 300_000)

    function onVisible() {
      if (document.visibilityState === "visible") void fetchNotifications()
    }
    document.addEventListener("visibilitychange", onVisible)

    return () => {
      clearInterval(interval)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [idToken])

  async function markAllRead() {
    if (!idToken || unreadCount === 0 || marking) return
    setMarking(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/notifications/mark-read`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({}),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setNotifications((prev) => prev.map((n) => ({ ...n, read: 1 as const })))
      setUnreadCount(0)
    } catch (err) {
      console.error("[hub] mark notifications read failed:", err)
      showToast("Couldn't mark notifications as read — check your connection and try again", "error")
    } finally {
      setMarking(false)
    }
  }

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "9px 14px",
          borderBottom: "1px solid var(--color-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <h3 style={{ margin: 0 }}>Notifications</h3>
          {unreadCount > 0 && (
            <span
              // Status indicator, not a commit — demoted from saturated lime
              // fill to an outlined tint per the codified lime rule in CLAUDE.md.
              style={{
                fontSize: 10,
                fontWeight: 600,
                background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                color: "var(--color-lime)",
                border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                borderRadius: 10,
                padding: "0 6px",
                lineHeight: 1.5,
              }}
            >
              {unreadCount}
            </span>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={markAllRead}
            disabled={marking}
            style={{
              fontSize: 10,
              color: "var(--color-text-faint)",
              background: "none",
              border: "none",
              cursor: marking ? "wait" : "pointer",
              padding: 0,
              display: "flex",
              alignItems: "center",
              gap: 3,
            }}
          >
            <Check size={10} />
            Mark all read
          </button>
        )}
      </div>

      {/* List — condensed to 4 on dashboard rail; full list at /notifications */}
      {notifications.length === 0 ? (
        <div
          style={{
            padding: "24px 14px",
            textAlign: "center",
            color: "var(--color-text-faint)",
            fontSize: 12,
          }}
        >
          All caught up
        </div>
      ) : (
        <div>
          {notifications.slice(0, 4).map((n) => {
            const Icon   = TYPE_ICON[n.type] ?? Bell
            const unread = n.read === 0
            return (
              <Link
                key={n.notif_id}
                href={normalizeNotifLink(n.link)}
                style={{
                  display: "flex",
                  gap: 9,
                  padding: "8px 14px",
                  borderBottom: "1px solid var(--color-border-subtle)",
                  background: unread
                    ? "color-mix(in srgb, var(--color-lime) 4%, transparent)"
                    : "transparent",
                  textDecoration: "none",
                  color: "inherit",
                }}
                className="hover:bg-[--color-elevated]"
              >
                {/* Icon */}
                <div style={{ flexShrink: 0, marginTop: 2 }}>
                  <Icon size={12} style={{ color: "var(--color-text-faint)" }} />
                </div>

                {/* Text */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: unread ? 500 : 400,
                      color: "var(--color-text)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {n.title}
                  </div>
                  {n.message && (
                    <div
                      style={{
                        fontSize: 10,
                        color: "var(--color-text-faint)",
                        lineHeight: 1.35,
                        marginTop: 2,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {n.message}
                    </div>
                  )}
                </div>

                {/* Timestamp */}
                <div
                  style={{
                    flexShrink: 0,
                    fontSize: 10,
                    color: "var(--color-text-faint)",
                    paddingTop: 2,
                  }}
                >
                  {relativeTime(n.timestamp)}
                </div>
              </Link>
            )
          })}
          {notifications.length > 4 && (
            <div
              style={{
                padding: "7px 14px",
                fontSize: 10,
                color: "var(--color-text-faint)",
                textAlign: "center",
                borderTop: "1px solid var(--color-border-subtle)",
              }}
            >
              {notifications.length - 4} more — open the bell for the full list
            </div>
          )}
        </div>
      )}
    </div>
  )
}
