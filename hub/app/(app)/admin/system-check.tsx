"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { formatApiError } from "@/lib/errors"

/**
 * Admin-only system probe. Streamlit parity: the Scripts tab's
 * "Developer Tools → Run System Check" expander, surfaced on the
 * Admin page where it logically belongs for the Next.js layout.
 *
 * Runs in parallel: health endpoint (backend + DB), then the full
 * sync trigger so editors can see at a glance whether Ollama, Sheets,
 * and the FastAPI DB are talking to each other.
 */
export function SystemCheck({ idToken: serverIdToken }: { idToken?: string }) {
  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [running, setRunning] = useState(false)
  const [healthResult, setHealthResult] = useState<{ status: string; version: string; syncs: Record<string, unknown> } | null>(null)
  const [syncResult, setSyncResult] = useState<{ status: string; results: Record<string, number | string> } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function runCheck(withSync: boolean) {
    setRunning(true)
    setError(null)
    setHealthResult(null)
    setSyncResult(null)
    try {
      const h = await client.health()
      setHealthResult(h)
      if (withSync) {
        const s = await client.sync.trigger()
        setSyncResult(s)
      }
    } catch (e) {
      setError(formatApiError(e, "System check"))
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="ec-block">
      <header><h2>System Check</h2></header>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => runCheck(false)}
            disabled={running}
            style={{
              padding: "6px 12px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.04em",
              borderRadius: 4,
              background: running ? "var(--color-elevated)" : "var(--color-lime)",
              color: running ? "var(--color-text-muted)" : "var(--color-lime-ink)",
              border: "none",
              cursor: running ? "wait" : "pointer",
            }}
          >
            {running ? "Checking…" : "Run Health Check"}
          </button>
          <button
            type="button"
            onClick={() => runCheck(true)}
            disabled={running}
            title="Health check + force a full Sheets → DB resync"
            style={{
              padding: "6px 12px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.04em",
              borderRadius: 4,
              background: "transparent",
              color: "var(--color-text)",
              border: "1px solid var(--color-border)",
              cursor: running ? "wait" : "pointer",
            }}
          >
            Force Full Sync
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 4,
              background: "color-mix(in srgb, var(--color-err) 10%, transparent)",
              border: "1px solid color-mix(in srgb, var(--color-err) 25%, transparent)",
              color: "var(--color-err)",
              fontSize: 11,
            }}
          >
            {error}
          </div>
        )}

        {healthResult && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 4,
              background: "var(--color-elevated)",
              fontSize: 11,
              color: "var(--color-text)",
              lineHeight: 1.6,
            }}
          >
            <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
              <StatusDot ok={healthResult.status === "ok"} />
              <span>API <strong>{healthResult.status}</strong> · version <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>{healthResult.version}</span></span>
            </div>
            {Object.entries(healthResult.syncs ?? {}).map(([source, infoRaw]) => {
              const info = infoRaw as { status?: string; rows?: number; last_synced?: string }
              const ok = !info.status || info.status === "ok" || info.status === "synced"
              return (
                <div key={source} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <StatusDot ok={ok} />
                  <span style={{ minWidth: 120 }}>{source}</span>
                  <span style={{ color: "var(--color-text-muted)", fontVariantNumeric: "tabular-nums" }}>
                    {info.rows !== undefined ? `${info.rows.toLocaleString()} rows` : info.status ?? "—"}
                  </span>
                  {info.last_synced && (
                    <span style={{ marginLeft: "auto", color: "var(--color-text-faint)", fontSize: 10, fontFamily: "var(--font-mono)" }}>
                      {info.last_synced}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {syncResult && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 4,
              background: "color-mix(in srgb, var(--color-ok) 6%, transparent)",
              border: "1px solid color-mix(in srgb, var(--color-ok) 22%, transparent)",
              fontSize: 11,
              color: "var(--color-text)",
            }}
          >
            <div style={{ marginBottom: 4, fontWeight: 600, color: "var(--color-ok)" }}>
              Sync {syncResult.status}
            </div>
            {Object.entries(syncResult.results ?? {}).map(([src, count]) => (
              <div key={src} style={{ display: "flex", gap: 10 }}>
                <span style={{ minWidth: 120, color: "var(--color-text-muted)" }}>{src}</span>
                <span style={{ color: "var(--color-text)", fontVariantNumeric: "tabular-nums" }}>{String(count)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: ok ? "var(--color-ok)" : "var(--color-err)",
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  )
}
