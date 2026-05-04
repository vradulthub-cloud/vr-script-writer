"use client"

import { useEffect, useState } from "react"
import { Send, Save, AlertCircle, CheckCircle2, ExternalLink } from "lucide-react"
import { api, type TeamsIntegration } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { formatApiError } from "@/lib/errors"

/**
 * Admin-only integrations panel.
 *
 * Today this manages the Microsoft Teams webhook URL (used by the
 * notification dispatcher to broadcast events) and the hub_base_url
 * (prepended to in-app links so Teams cards open the right page).
 *
 * Future: Slack webhook, SMTP creds, etc. — same shape, one card per
 * integration.
 */
export function IntegrationsPanel({ idToken: serverIdToken }: { idToken?: string }) {
  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [teams, setTeams] = useState<TeamsIntegration | null>(null)
  const [teamsUrl, setTeamsUrl] = useState("")
  const [teamsBusy, setTeamsBusy] = useState(false)
  const [teamsMsg, setTeamsMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null)

  const [baseUrl, setBaseUrl] = useState("")
  const [baseUrlMeta, setBaseUrlMeta] = useState<{ updated_by: string; updated_at: string }>({ updated_by: "", updated_at: "" })
  const [baseUrlBusy, setBaseUrlBusy] = useState(false)
  const [baseUrlMsg, setBaseUrlMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null)

  useEffect(() => {
    if (!idToken) return
    let cancelled = false
    Promise.all([client.integrations.teams.get(), client.integrations.hubBaseUrl.get()])
      .then(([t, b]) => {
        if (cancelled) return
        setTeams(t)
        setBaseUrl(b.url)
        setBaseUrlMeta({ updated_by: b.updated_by, updated_at: b.updated_at })
      })
      .catch(() => { /* silent — panel handles empty state below */ })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idToken])

  async function saveTeams() {
    if (teamsBusy) return
    setTeamsBusy(true)
    setTeamsMsg(null)
    try {
      const res = await client.integrations.teams.update(teamsUrl.trim())
      setTeams({
        configured: res.configured,
        url_preview: res.url_preview,
        updated_by: teams?.updated_by ?? "",
        updated_at: new Date().toISOString(),
      })
      setTeamsUrl("")
      setTeamsMsg({ kind: "ok", text: res.configured ? "Webhook saved." : "Webhook cleared — Teams notifications disabled." })
    } catch (e) {
      setTeamsMsg({ kind: "err", text: formatApiError(e, "Save webhook") })
    } finally {
      setTeamsBusy(false)
    }
  }

  async function testTeams() {
    if (teamsBusy) return
    setTeamsBusy(true)
    setTeamsMsg(null)
    try {
      await client.integrations.teams.test()
      setTeamsMsg({ kind: "ok", text: "Test message sent — check the Teams channel." })
    } catch (e) {
      setTeamsMsg({ kind: "err", text: formatApiError(e, "Send test") })
    } finally {
      setTeamsBusy(false)
    }
  }

  async function saveBaseUrl() {
    if (baseUrlBusy) return
    setBaseUrlBusy(true)
    setBaseUrlMsg(null)
    try {
      const res = await client.integrations.hubBaseUrl.update(baseUrl.trim())
      setBaseUrl(res.url)
      setBaseUrlMeta({ updated_by: "you", updated_at: new Date().toISOString() })
      setBaseUrlMsg({ kind: "ok", text: "Base URL saved." })
    } catch (e) {
      setBaseUrlMsg({ kind: "err", text: formatApiError(e, "Save base URL") })
    } finally {
      setBaseUrlBusy(false)
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Teams webhook ─────────────────────────────────────────────────── */}
      <section className="ec-block">
        <header>
          <h2>Microsoft Teams</h2>
        </header>
        <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.5 }}>
            Connect a Teams channel via a Power Automate <strong>Workflows</strong> webhook (recommended) or a legacy{" "}
            <strong>Incoming Webhook</strong> connector. Once configured, every user with the
            Teams channel enabled in their notification preferences will see broadcast messages
            for their subscribed events.
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11 }}>
            {teams?.configured ? (
              <>
                <CheckCircle2 size={13} aria-hidden="true" style={{ color: "var(--color-ok)" }} />
                <span style={{ color: "var(--color-ok)", fontWeight: 600 }}>Configured</span>
                <span style={{ color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
                  {teams.url_preview}
                </span>
                {teams.updated_by && (
                  <span style={{ color: "var(--color-text-faint)" }}>
                    · saved by {teams.updated_by}
                  </span>
                )}
              </>
            ) : (
              <>
                <AlertCircle size={13} aria-hidden="true" style={{ color: "var(--color-warn)" }} />
                <span style={{ color: "var(--color-warn)", fontWeight: 600 }}>Not configured</span>
              </>
            )}
          </div>

          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11 }}>
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", letterSpacing: "0.04em", textTransform: "uppercase", fontSize: 10 }}>
              Webhook URL
            </span>
            <input
              type="url"
              value={teamsUrl}
              onChange={e => setTeamsUrl(e.target.value)}
              placeholder="https://prod-XX.azureconnectors.com/…/triggers/manual/paths/invoke?…"
              style={{
                background: "var(--color-base)",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                padding: "8px 10px",
                fontSize: 12,
                color: "var(--color-text)",
                fontFamily: "var(--font-mono)",
                outline: "none",
              }}
            />
            <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
              Paste a fresh URL to update, or leave blank and save to clear it.
            </span>
          </label>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              onClick={saveTeams}
              disabled={teamsBusy}
              className="ec-btn"
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                background: "var(--color-lime)", color: "#000", fontWeight: 700,
                border: "none", padding: "6px 12px", borderRadius: 4, fontSize: 11,
                cursor: teamsBusy ? "wait" : "pointer", opacity: teamsBusy ? 0.5 : 1,
              }}
            >
              <Save size={11} aria-hidden="true" />
              Save webhook
            </button>
            <button
              onClick={testTeams}
              disabled={teamsBusy || !teams?.configured}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                background: "transparent", color: "var(--color-text)",
                border: "1px solid var(--color-border)", padding: "6px 12px", borderRadius: 4, fontSize: 11,
                cursor: teamsBusy || !teams?.configured ? "not-allowed" : "pointer",
                opacity: teamsBusy || !teams?.configured ? 0.4 : 1,
              }}
            >
              <Send size={11} aria-hidden="true" />
              Send test message
            </button>
            <a
              href="https://learn.microsoft.com/en-us/power-automate/teams/teams-actions-triggers"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                fontSize: 11, color: "var(--color-text-muted)",
                textDecoration: "none", padding: "6px 0",
              }}
            >
              <ExternalLink size={11} aria-hidden="true" />
              Power Automate setup guide
            </a>
          </div>

          {teamsMsg && (
            <div
              style={{
                padding: "6px 10px", fontSize: 11, borderRadius: 4,
                background: teamsMsg.kind === "ok"
                  ? "color-mix(in srgb, var(--color-ok) 10%, transparent)"
                  : "color-mix(in srgb, var(--color-err) 10%, transparent)",
                color: teamsMsg.kind === "ok" ? "var(--color-ok)" : "var(--color-err)",
                border: `1px solid color-mix(in srgb, ${teamsMsg.kind === "ok" ? "var(--color-ok)" : "var(--color-err)"} 25%, transparent)`,
              }}
            >
              {teamsMsg.text}
            </div>
          )}
        </div>
      </section>

      {/* Hub base URL ─────────────────────────────────────────────────── */}
      <section className="ec-block">
        <header>
          <h2>Hub base URL</h2>
        </header>
        <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.5 }}>
            Public URL of this hub. Used to build absolute links inside Teams messages
            and email so recipients can click through to the right page.
          </p>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11 }}>
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", letterSpacing: "0.04em", textTransform: "uppercase", fontSize: 10 }}>
              Base URL
            </span>
            <input
              type="url"
              value={baseUrl}
              onChange={e => setBaseUrl(e.target.value)}
              placeholder="https://eclatech-hub.vercel.app"
              style={{
                background: "var(--color-base)",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                padding: "8px 10px",
                fontSize: 12,
                color: "var(--color-text)",
                fontFamily: "var(--font-mono)",
                outline: "none",
              }}
            />
            {baseUrlMeta.updated_by && (
              <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                Last updated by {baseUrlMeta.updated_by}
              </span>
            )}
          </label>
          <div>
            <button
              onClick={saveBaseUrl}
              disabled={baseUrlBusy}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                background: "var(--color-lime)", color: "#000", fontWeight: 700,
                border: "none", padding: "6px 12px", borderRadius: 4, fontSize: 11,
                cursor: baseUrlBusy ? "wait" : "pointer", opacity: baseUrlBusy ? 0.5 : 1,
              }}
            >
              <Save size={11} aria-hidden="true" />
              Save URL
            </button>
          </div>
          {baseUrlMsg && (
            <div
              style={{
                padding: "6px 10px", fontSize: 11, borderRadius: 4,
                background: baseUrlMsg.kind === "ok"
                  ? "color-mix(in srgb, var(--color-ok) 10%, transparent)"
                  : "color-mix(in srgb, var(--color-err) 10%, transparent)",
                color: baseUrlMsg.kind === "ok" ? "var(--color-ok)" : "var(--color-err)",
                border: `1px solid color-mix(in srgb, ${baseUrlMsg.kind === "ok" ? "var(--color-ok)" : "var(--color-err)"} 25%, transparent)`,
              }}
            >
              {baseUrlMsg.text}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
