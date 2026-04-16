"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Bell, Ticket, RefreshCw, UserCheck, ClipboardList, CheckCircle, Pin } from "lucide-react"
import { signOut } from "next-auth/react"
import { api, ApiError, type Notification } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"

const TYPE_ICONS: Record<string, typeof Bell> = {
  ticket_created: Ticket,
  ticket_status: RefreshCw,
  ticket_assigned: UserCheck,
  approval_submitted: ClipboardList,
  approval_decided: CheckCircle,
}
const FallbackIcon = Pin

interface NotificationBellProps {
  idToken: string | undefined
}

export function NotificationBell({ idToken: serverToken }: NotificationBellProps) {
  const idToken = useIdToken(serverToken)
  const client = api(idToken ?? null)

  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  // Poll unread count every 60s
  const fetchUnread = useCallback(async () => {
    try {
      const { count } = await client.notifications.unreadCount()
      setUnread(count)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        // Token is dead — sign out so the user gets redirected to login cleanly
        signOut({ redirectTo: "/login" })
      }
      // Other failures: silently ignore — bell just won't show a badge
    }
  }, [idToken])

  useEffect(() => {
    fetchUnread()
    const interval = setInterval(fetchUnread, 60_000)
    return () => clearInterval(interval)
  }, [fetchUnread])

  // Fetch full list when panel opens
  useEffect(() => {
    if (!open) return
    setLoading(true)
    client.notifications.list(30).then((data) => {
      setNotifications(data)
      setLoading(false)
    }).catch((e) => {
      console.warn("[notifications] Failed to load list:", e)
      setLoading(false)
    })
  }, [open, idToken])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [open])

  async function markAllRead() {
    await client.notifications.markRead()
    setUnread(0)
    setNotifications((prev) => prev.map((n) => ({ ...n, read: 1 })))
  }

  function timeAgo(timestamp: string): string {
    const diff = Date.now() - new Date(timestamp + "Z").getTime()
    const mins = Math.floor(diff / 60_000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  }

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="p-1.5 rounded transition-colors hover:bg-[--color-elevated] relative"
        style={{ color: "var(--color-text-muted)" }}
        aria-label="Notifications"
      >
        <Bell size={14} />
        {unread > 0 && (
          <span
            className="absolute flex items-center justify-center rounded-full font-semibold"
            style={{
              top: 2,
              right: 2,
              minWidth: 14,
              height: 14,
              fontSize: 9,
              background: "var(--color-err)",
              color: "var(--color-text)",
              padding: "0 3px",
              animation: "countBounce 0.4s var(--ease-out-quart)",
            }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          className="absolute right-0 overflow-hidden"
          data-dropdown
          style={{
            top: "calc(100% + 6px)",
            width: 340,
            maxHeight: 420,
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            zIndex: 100,
            boxShadow: "0 8px 24px rgba(0,0,0,.4)",
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-3 py-2"
            style={{ borderBottom: "1px solid var(--color-border)" }}
          >
            <span
              className="font-semibold"
              style={{ fontSize: 12, color: "var(--color-text)" }}
            >
              Notifications
            </span>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="transition-colors hover:opacity-80"
                style={{ fontSize: 11, color: "var(--color-lime)" }}
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="overflow-y-auto" style={{ maxHeight: 370 }}>
            {loading && (
              <div className="py-6 text-center" style={{ color: "var(--color-text-faint)", fontSize: 12 }}>
                Loading...
              </div>
            )}
            {!loading && notifications.length === 0 && (
              <div className="py-6 text-center" style={{ color: "var(--color-text-faint)", fontSize: 12 }}>
                No notifications
              </div>
            )}
            {!loading && notifications.map((n) => (
              <div
                key={n.notif_id}
                className="px-3 py-2 transition-colors hover:bg-[--color-elevated]"
                style={{
                  borderBottom: "1px solid var(--color-border-subtle, var(--color-border))",
                  opacity: n.read ? 0.6 : 1,
                }}
              >
                <div className="flex items-start gap-2">
                  {(() => {
                    const Icon = TYPE_ICONS[n.type] ?? FallbackIcon
                    return <Icon size={13} style={{ color: "var(--color-text-muted)", flexShrink: 0, marginTop: 1 }} />
                  })()}
                  <div className="flex-1 min-w-0">
                    <div
                      className="font-medium truncate"
                      style={{ fontSize: 12, color: "var(--color-text)" }}
                    >
                      {n.title}
                    </div>
                    <div
                      className="truncate"
                      style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 1 }}
                    >
                      {n.message}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 2 }}>
                      {timeAgo(n.timestamp)}
                    </div>
                  </div>
                  {!n.read && (
                    <span
                      className="rounded-full shrink-0"
                      style={{
                        width: 6,
                        height: 6,
                        background: "var(--color-lime)",
                        marginTop: 4,
                      }}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
