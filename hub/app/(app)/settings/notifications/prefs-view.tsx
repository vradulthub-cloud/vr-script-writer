"use client"

import { useState } from "react"
import { Bell, MessageSquare, Mail } from "lucide-react"
import { api, type NotificationPref, type NotificationChannel } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { formatApiError } from "@/lib/errors"
import { PageHeader } from "@/components/ui/page-header"
import { ErrorAlert } from "@/components/ui/error-alert"

const CHANNELS: Array<{ key: NotificationChannel; label: string; icon: typeof Bell; hint: string }> = [
  { key: "in_app", label: "In-app",  icon: Bell,           hint: "Notification bell + dashboard feed" },
  { key: "teams",  label: "Teams",   icon: MessageSquare,  hint: "Posts to the configured Teams channel" },
  { key: "email",  label: "Email",   icon: Mail,           hint: "Sends to your account email (coming soon)" },
]

export function PrefsView({
  initial,
  initialError,
  idToken: serverIdToken,
}: {
  initial: NotificationPref[]
  initialError: string | null
  idToken?: string
}) {
  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [prefs, setPrefs] = useState<NotificationPref[]>(initial)
  const [savingType, setSavingType] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(initialError)

  async function persist(p: NotificationPref) {
    setSavingType(p.event_type)
    setError(null)
    try {
      const updated = await client.notifications.updatePref({
        event_type: p.event_type,
        channels: p.channels,
        enabled: p.enabled,
      })
      setPrefs(updated)
    } catch (e) {
      setError(formatApiError(e, "Save preference"))
      // Revert on failure by refetching from server
      try {
        setPrefs(await client.notifications.prefs())
      } catch { /* keep optimistic state if refetch also fails */ }
    } finally {
      setSavingType(null)
    }
  }

  function toggleEnabled(p: NotificationPref) {
    const next = { ...p, enabled: !p.enabled }
    setPrefs(prev => prev.map(x => x.event_type === p.event_type ? next : x))
    void persist(next)
  }

  function toggleChannel(p: NotificationPref, channel: NotificationChannel) {
    const has = p.channels.includes(channel)
    const channels = has
      ? p.channels.filter(c => c !== channel)
      : [...p.channels, channel]
    const next = { ...p, channels }
    setPrefs(prev => prev.map(x => x.event_type === p.event_type ? next : x))
    void persist(next)
  }

  return (
    <div style={{ padding: "0 0 32px", maxWidth: 880 }}>
      <PageHeader
        eyebrow="Settings"
        title="Notifications"
        subtitle="Choose which events you want to be notified about and how each one reaches you. Per-user — only affects your account."
      />

      {error && <div style={{ marginBottom: 16 }}><ErrorAlert>{error}</ErrorAlert></div>}

      <section className="ec-block">
        <header><h2>Event subscriptions</h2></header>
        <div style={{ padding: 0 }}>
          {/* Header row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr repeat(3, 90px) 64px",
              gap: 12,
              padding: "10px 14px",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "var(--color-text-faint)",
              borderBottom: "1px solid var(--color-border)",
              background: "var(--color-elevated)",
            }}
          >
            <div>Event</div>
            {CHANNELS.map(c => <div key={c.key} style={{ textAlign: "center" }}>{c.label}</div>)}
            <div style={{ textAlign: "center" }}>On</div>
          </div>

          {prefs.length === 0 && (
            <div style={{ padding: 24, fontSize: 12, color: "var(--color-text-faint)", textAlign: "center" }}>
              No event types registered yet.
            </div>
          )}

          {prefs.map(p => (
            <div
              key={p.event_type}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr repeat(3, 90px) 64px",
                gap: 12,
                padding: "12px 14px",
                borderBottom: "1px solid var(--color-border-subtle, var(--color-border))",
                alignItems: "center",
                opacity: p.enabled ? 1 : 0.5,
                transition: "opacity 120ms ease",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text)" }}>{p.label}</div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>{p.description}</div>
              </div>

              {CHANNELS.map(c => {
                const enabled = p.channels.includes(c.key)
                const Icon = c.icon
                const disabled = !p.enabled || c.key === "email" /* email backend pending */
                return (
                  <button
                    key={c.key}
                    onClick={() => !disabled && toggleChannel(p, c.key)}
                    title={c.hint}
                    aria-pressed={enabled}
                    disabled={disabled || savingType === p.event_type}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 4,
                      height: 28,
                      borderRadius: 4,
                      background: enabled
                        ? "color-mix(in srgb, var(--color-lime) 18%, transparent)"
                        : "var(--color-base)",
                      color: enabled ? "var(--color-lime)" : "var(--color-text-muted)",
                      border: `1px solid ${enabled ? "color-mix(in srgb, var(--color-lime) 35%, transparent)" : "var(--color-border)"}`,
                      cursor: disabled ? "not-allowed" : "pointer",
                      opacity: disabled ? 0.4 : 1,
                      fontSize: 11,
                    }}
                  >
                    <Icon size={11} aria-hidden="true" />
                  </button>
                )
              })}

              <div style={{ display: "flex", justifyContent: "center" }}>
                <button
                  role="switch"
                  aria-checked={p.enabled}
                  aria-label={`${p.enabled ? "Disable" : "Enable"} ${p.label}`}
                  onClick={() => toggleEnabled(p)}
                  disabled={savingType === p.event_type}
                  style={{
                    width: 36,
                    height: 20,
                    borderRadius: 999,
                    background: p.enabled ? "var(--color-lime)" : "var(--color-border)",
                    border: "none",
                    position: "relative",
                    cursor: savingType === p.event_type ? "wait" : "pointer",
                    transition: "background-color 140ms ease",
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      position: "absolute",
                      top: 2,
                      left: p.enabled ? 18 : 2,
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      background: "#000",
                      transition: "left 140ms cubic-bezier(0.16, 1, 0.3, 1)",
                    }}
                  />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <p style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 14, lineHeight: 1.5 }}>
        Tip: ask an admin to set up the Microsoft Teams webhook in <strong>Admin → Integrations</strong>{" "}
        before enabling the Teams channel — otherwise your Teams subscriptions are silent. The email
        channel is reserved for an upcoming SMTP integration and is currently inactive.
      </p>
    </div>
  )
}
