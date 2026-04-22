"use client"

import { useEffect, useState, useCallback } from "react"
import { api } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"

type SyncMeta = {
  source: string
  last_synced_at?: string
  row_count?: number
  status?: string
  error?: string
}

/** Per-source sync controls. Replaces the static "Syncs" sidebar so admins
 *  can re-pull a specific data source after a Sheet edit without triggering
 *  a full sync (which can take >30s when MEGA scenes are involved). */
export function SyncPanel({
  initial,
  idToken: serverIdToken,
}: {
  initial: SyncMeta[]
  idToken?: string
}) {
  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [rows, setRows] = useState<SyncMeta[]>(initial)
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ source: string; ok: boolean; text: string } | null>(null)

  const refresh = useCallback(async () => {
    try {
      const next = await client.sync.status()
      setRows(next as SyncMeta[])
    } catch {
      // Non-fatal — we still show the previous values.
    }
  }, [client])

  useEffect(() => {
    // Refresh once on mount in case the server-rendered values are stale.
    refresh()
  }, [refresh])

  async function trigger(source: string) {
    setBusy(source)
    setMsg(null)
    try {
      const res = await client.syncOne(source)
      setMsg({ source, ok: true, text: `${res.row_count.toLocaleString()} rows` })
      refresh()
    } catch (e) {
      setMsg({ source, ok: false, text: e instanceof Error ? e.message : "Failed" })
    } finally {
      setBusy(null)
    }
  }

  if (rows.length === 0) return null

  return (
    <section className="ec-block">
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2>Syncs</h2>
        <a
          onClick={refresh}
          style={{ cursor: "pointer", fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-muted)" }}
        >
          Refresh
        </a>
      </header>
      <ul className="ec-list">
        {rows.map(r => {
          const ok = !r.status || r.status === "ok" || r.status === "synced"
          const isBusy = busy === r.source
          const line = msg && msg.source === r.source ? msg.text : (r.row_count !== undefined ? `${r.row_count.toLocaleString()} rows` : r.status ?? "—")
          const lineColor = msg && msg.source === r.source
            ? (msg.ok ? "var(--color-ok)" : "var(--color-err)")
            : "var(--color-text-faint)"
          return (
            <li key={r.source} style={{ gridTemplateColumns: "10px 1fr auto auto" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: ok ? "var(--color-ok)" : "var(--color-err)" }} />
              <span style={{ fontSize: 12, color: "var(--color-text)" }}>{r.source}</span>
              <span style={{ fontSize: 10, color: lineColor, fontVariantNumeric: "tabular-nums", letterSpacing: "0.1em", textTransform: "uppercase", marginRight: 10 }}>
                {line}
              </span>
              <button
                type="button"
                onClick={() => trigger(r.source)}
                disabled={isBusy || !!busy}
                title={`Re-sync ${r.source} from Google Sheets`}
                style={{
                  background: "transparent",
                  border: "1px solid var(--color-border)",
                  color: isBusy ? "var(--color-lime)" : "var(--color-text-muted)",
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  padding: "3px 8px",
                  cursor: isBusy || busy ? "wait" : "pointer",
                  opacity: !!busy && !isBusy ? 0.4 : 1,
                }}
              >
                {isBusy ? "Syncing…" : "Sync"}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
