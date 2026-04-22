import { auth } from "@/auth"
import { api, type UserProfile, type TicketStats, type SceneStats, type TaskStats } from "@/lib/api"
import { requireAdmin } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { UsersPanel } from "./users-panel"
import { SystemCheck } from "./system-check"
import { SyncPanel } from "./sync-panel"
import { AuditLogPanel } from "./audit-log-panel"
import { TasksPanel } from "./tasks-panel"

export const dynamic = "force-dynamic"

export default async function AdminPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const me = await requireAdmin(idToken)
  const client = api(session)
  const v2 = await isEclatechV2()

  let users: UserProfile[] = []
  let error: string | null = null
  let health: { status: string; version: string; syncs: Record<string, unknown> } | null = null
  let ticketStats: TicketStats | null = null
  let sceneStats: SceneStats | null = null
  let taskStats: TaskStats | null = null

  // One Promise.allSettled gathers everything in parallel — v2 admins see the
  // quick-stats strip + audit log + tasks panel, so the page is API-heavy.
  // We tolerate any single failure rather than blanking the whole page.
  const [usersRes, healthRes, ticketRes, sceneRes, taskRes] = await Promise.allSettled([
    client.users.list(),
    v2 ? client.health() : Promise.resolve(null),
    v2 ? client.tickets.stats() : Promise.resolve(null),
    v2 ? client.scenes.stats() : Promise.resolve(null),
    v2 ? client.tasks.stats() : Promise.resolve(null),
  ])
  if (usersRes.status === "fulfilled") users = usersRes.value
  else error = usersRes.reason instanceof Error ? usersRes.reason.message : "Failed to load users"
  if (v2 && healthRes.status === "fulfilled") health = healthRes.value
  if (v2 && ticketRes.status === "fulfilled") ticketStats = ticketRes.value
  if (v2 && sceneRes.status === "fulfilled") sceneStats = sceneRes.value
  if (v2 && taskRes.status === "fulfilled") taskStats = taskRes.value

  const panel = <UsersPanel users={users} error={error} idToken={idToken} currentEmail={me.email} />
  if (!v2) return panel

  const activeCount = users.filter(u => u.role).length
  const adminCount = users.filter(u => (u.role ?? "").toLowerCase() === "admin").length
  const editorCount = users.filter(u => (u.role ?? "").toLowerCase() === "editor").length

  // Open tickets = anything not Closed/Rejected. The stats endpoint groups by
  // status so we sum the active buckets rather than asking for "open" — fewer
  // round-trips, and the same number we'd compute on the Tickets page.
  const openTickets = ticketStats
    ? (ticketStats["New"] ?? 0) + (ticketStats["Approved"] ?? 0) +
      (ticketStats["In Progress"] ?? 0) + (ticketStats["In Review"] ?? 0)
    : null

  // Freshest sync — gives admins a one-glance "are we current?". Stale syncs
  // are the most common silent failure mode (sheet went down, retries
  // exhausted, but the UI keeps serving cached data).
  const newestSync = newestSyncAge(health?.syncs)

  return (
    <div className="ec-cols">
      <div className="ec-col">{panel}</div>
      <div className="ec-col">
        <section className="ec-block ec-inverted">
          <header><h2>System</h2></header>
          <div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <AdminStat label="Version" value={health?.version ?? "—"} mono />
            <AdminStat label="Status" value={health?.status ?? "—"} />
            <AdminStat label="Users" value={`${activeCount}`} sub={`${adminCount} admin · ${editorCount} editor`} />
            <AdminStat
              label="Open tickets"
              value={openTickets !== null ? `${openTickets}` : "—"}
              sub={ticketStats ? `${ticketStats["Closed"] ?? 0} closed total` : undefined}
            />
            <AdminStat
              label="Scenes"
              value={sceneStats ? sceneStats.total.toLocaleString() : "—"}
              sub={sceneStats ? `${sceneStats.complete} complete · ${sceneStats.missing_any} need work` : undefined}
            />
            <AdminStat
              label="Tasks"
              value={taskStats ? `${(taskStats.pending + taskStats.running)}` : "—"}
              sub={taskStats ? `${taskStats.running} running · ${taskStats.pending} queued` : undefined}
            />
            <AdminStat
              label="Latest sync"
              value={newestSync.value}
              sub={newestSync.sub}
            />
          </div>
        </section>

        <SystemCheck idToken={idToken} />

        {health?.syncs && Object.keys(health.syncs).length > 0 && (
          <SyncPanel
            initial={Object.entries(health.syncs).map(([source, infoRaw]) => {
              const info = infoRaw as { status?: string; row_count?: number; last_synced_at?: string }
              return { source, ...info }
            })}
            idToken={idToken}
          />
        )}

        <TasksPanel idToken={idToken} />
        <AuditLogPanel idToken={idToken} />
      </div>
    </div>
  )
}

/**
 * Walk the syncs map, find the most recent timestamp, and report it as a
 * relative age. Returns "—" if no syncs have ever run (fresh DB).
 */
function newestSyncAge(syncs?: Record<string, unknown> | null): { value: string; sub?: string } {
  if (!syncs) return { value: "—" }
  let newest = 0
  let newestSource = ""
  for (const [source, infoRaw] of Object.entries(syncs)) {
    const info = infoRaw as { last_synced_at?: string; last_synced?: string }
    const ts = info?.last_synced_at ?? info?.last_synced ?? ""
    if (!ts) continue
    const ms = new Date(ts).getTime()
    if (!Number.isFinite(ms) || ms <= newest) continue
    newest = ms
    newestSource = source
  }
  if (!newest) return { value: "—" }
  const ageSec = Math.max(0, Math.floor((Date.now() - newest) / 1000))
  let label: string
  if (ageSec < 60) label = `${ageSec}s ago`
  else if (ageSec < 3600) label = `${Math.floor(ageSec / 60)}m ago`
  else if (ageSec < 86400) label = `${Math.floor(ageSec / 3600)}h ago`
  else label = `${Math.floor(ageSec / 86400)}d ago`
  return { value: label, sub: newestSource ? `from ${newestSource}` : undefined }
}

function AdminStat({ label, value, sub, mono }: { label: string; value: string; sub?: string; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(255,255,255,0.45)" }}>
        {label}
      </div>
      <div
        style={{
          marginTop: 4,
          fontWeight: 800,
          fontSize: 22,
          letterSpacing: "-0.03em",
          fontFamily: mono ? "var(--font-mono)" : "var(--font-display-hero)",
          lineHeight: 1.05,
          // Long version strings ("2.0.0") fit; tablet widths can clip otherwise.
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={value}
      >
        {value}
      </div>
      {sub && (
        <div style={{ marginTop: 2, fontSize: 9, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(255,255,255,0.55)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={sub}>
          {sub}
        </div>
      )}
    </div>
  )
}
