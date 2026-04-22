"use client"

import { useEffect, useState, useMemo, useCallback } from "react"
import { api, type TaskRow } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { Panel } from "@/components/ui/panel"

/** Background task queue.
 *
 *  Reads /api/tasks/ — recent rows from the local SQLite `tasks` table
 *  (script_gen, desc_gen, mega_scan, comp_export, ...). This is a
 *  pure read view: cancel/retry buttons would need worker-side hooks
 *  that don't exist yet, and shipping a button that does nothing is
 *  worse than no button.
 *
 *  Polls every 8s while running tasks are present, otherwise idle.
 *  Rationale: completed tasks don't change, so polling is wasteful;
 *  but if there's anything pending or running, we want fresh progress
 *  bars without forcing a manual Refresh.
 */
export function TasksPanel({ idToken: serverIdToken }: { idToken?: string }) {
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [rows, setRows] = useState<TaskRow[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const list = await client.tasks.list({ limit: 25 })
      setRows(list)
      setErr(null)
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load tasks")
    } finally {
      setLoading(false)
    }
  }, [client])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Auto-poll only while there's live work — saves backend cycles otherwise.
  const hasLive = rows.some(r => r.status === "pending" || r.status === "running")
  useEffect(() => {
    if (!hasLive) return
    const id = setInterval(refresh, 8000)
    return () => clearInterval(id)
  }, [hasLive, refresh])

  return (
    <Panel>
      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--color-text)" }}>
            Background Tasks
          </h2>
          <span style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
            {hasLive ? "Live · auto-refresh" : "Idle · last 25"}
          </span>
        </div>
        {loading && <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>Loading…</div>}
        {err && <div style={{ fontSize: 12, color: "var(--color-err)" }}>{err}</div>}
        {!loading && !err && rows.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>No background tasks have run yet.</div>
        )}
        {!loading && !err && rows.length > 0 && (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            {rows.map(t => <TaskRowItem key={t.task_id} task={t} />)}
          </ul>
        )}
      </div>
    </Panel>
  )
}

function TaskRowItem({ task }: { task: TaskRow }) {
  const color = STATUS_COLOR[task.status] ?? "var(--color-text-faint)"
  const pct = Math.max(0, Math.min(1, task.progress)) * 100
  const isRunning = task.status === "running"

  return (
    <li
      style={{
        display: "grid",
        gridTemplateColumns: "8px 110px 1fr 80px",
        gap: 10,
        padding: "8px 10px",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 4,
        background: "var(--color-elevated)",
        alignItems: "center",
      }}
    >
      <span
        title={task.status}
        style={{
          width: 6, height: 6, borderRadius: "50%", background: color,
          boxShadow: isRunning ? `0 0 8px ${color}` : undefined,
        }}
      />
      <span style={{ fontSize: 11, color: "var(--color-text)", fontFamily: "var(--font-mono)", letterSpacing: "0.02em" }}>
        {task.task_type}
      </span>
      <div style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6, justifyContent: "space-between" }}>
          <span
            style={{
              fontSize: 11, color: "var(--color-text-muted)",
              overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis",
              fontFamily: "var(--font-mono)", letterSpacing: "0.02em",
            }}
            title={task.task_id}
          >
            {task.task_id}
          </span>
          {task.error && (
            <span
              title={task.error}
              style={{ fontSize: 10, color: "var(--color-err)", overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis", maxWidth: 240 }}
            >
              {task.error}
            </span>
          )}
        </div>
        {(isRunning || task.status === "pending") && (
          <div
            style={{
              height: 3, background: "color-mix(in srgb, var(--color-text) 8%, transparent)",
              borderRadius: 2, overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${pct}%`,
                height: "100%",
                background: color,
                transition: "width 250ms ease",
              }}
            />
          </div>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 1 }}>
        <span
          style={{
            fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
            color, whiteSpace: "nowrap",
          }}
        >
          {task.status}
        </span>
        <span style={{ fontSize: 9, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
          {ageOf(task)}
        </span>
      </div>
    </li>
  )
}

const STATUS_COLOR: Record<string, string> = {
  pending:   "var(--color-text-muted)",
  running:   "var(--color-lime)",
  completed: "var(--color-ok)",
  failed:    "var(--color-err)",
}

function ageOf(t: TaskRow): string {
  const ref = t.completed_at || t.started_at || t.created_at
  if (!ref) return "—"
  const d = new Date(ref)
  if (isNaN(d.getTime())) return ref
  const sec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000))
  if (sec < 60) return `${sec}s ago`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  return `${Math.floor(sec / 86400)}d ago`
}
