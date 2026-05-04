import { auth } from "@/auth"
import { api, type UserProfile, type TicketStats, type SceneStats, type TaskStats } from "@/lib/api"
import { requireAdmin } from "@/lib/rbac"
import { UsersPanel } from "./users-panel"
import { SystemCheck } from "./system-check"
import { SyncPanel } from "./sync-panel"
import { AuditLogPanel } from "./audit-log-panel"
import { TasksPanel } from "./tasks-panel"
import { PromptsPanel } from "./prompts-panel"
import { ComplianceW9Panel } from "./compliance-w9-panel"
import { IntegrationsPanel } from "./integrations-panel"
import { AdminTabs } from "./admin-tabs"
import { StatStrip, type StatTile } from "./stat-strip"

export const dynamic = "force-dynamic"

/**
 * Admin console — tabbed layout.
 *
 * Top: full-width quick-stats strip (visible across all tabs because health
 * is the kind of context admins want at a glance regardless of which task
 * they're doing).
 *
 * Tabs:
 *   1. Users      — the User Permissions table + add/remove flows
 *   2. System     — System Check + per-source sync triggers
 *   3. Activity   — Background tasks queue + permission audit log
 *   4. AI Prompts — edit description/title/script generation prompts
 *
 * The previous 2-column layout was cramped: a wide users table on the
 * left forced 5 panels into a single narrow column on the right. Tabs
 * give every section its own canvas without losing top-of-page health
 * context.
 */
export default async function AdminPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const me = await requireAdmin(idToken)
  const client = api(session)

  let users: UserProfile[] = []
  let error: string | null = null
  let health: { status: string; version: string; syncs: Record<string, unknown> } | null = null
  let ticketStats: TicketStats | null = null
  let sceneStats: SceneStats | null = null
  let taskStats: TaskStats | null = null

  const [usersRes, healthRes, ticketRes, sceneRes, taskRes] = await Promise.allSettled([
    client.users.list(),
    client.health(),
    client.tickets.stats(),
    client.scenes.stats(),
    client.tasks.stats(),
  ])
  if (usersRes.status === "fulfilled") users = usersRes.value
  else error = usersRes.reason instanceof Error ? usersRes.reason.message : "Failed to load users"
  if (healthRes.status === "fulfilled") health = healthRes.value
  if (ticketRes.status === "fulfilled") ticketStats = ticketRes.value
  if (sceneRes.status === "fulfilled") sceneStats = sceneRes.value
  if (taskRes.status === "fulfilled") taskStats = taskRes.value

  const usersPanel = (
    <UsersPanel users={users} error={error} idToken={idToken} currentEmail={me.email} />
  )

  const adminCount = users.filter(u => (u.role ?? "").toLowerCase() === "admin").length
  const editorCount = users.filter(u => (u.role ?? "").toLowerCase() === "editor").length
  const openTickets = ticketStats
    ? (ticketStats["New"] ?? 0) + (ticketStats["Approved"] ?? 0) +
      (ticketStats["In Progress"] ?? 0) + (ticketStats["In Review"] ?? 0)
    : null
  const newestSync = newestSyncAge(health?.syncs)
  const liveTasks = taskStats ? taskStats.pending + taskStats.running : null

  const stats: StatTile[] = [
    { label: "Version",      value: health?.version ?? "—", mono: true },
    { label: "Status",       value: health?.status ?? "—", accent: health?.status === "ok" ? "var(--color-ok)" : undefined },
    { label: "Users",        value: `${users.length}`, sub: `${adminCount} admin · ${editorCount} editor` },
    { label: "Open tickets", value: openTickets !== null ? `${openTickets}` : "—", sub: ticketStats ? `${ticketStats["Closed"] ?? 0} closed` : undefined },
    { label: "Scenes",       value: sceneStats ? sceneStats.total.toLocaleString() : "—", sub: sceneStats ? `${sceneStats.complete} complete` : undefined },
    { label: "Tasks",        value: liveTasks !== null ? `${liveTasks}` : "—", sub: taskStats ? `${taskStats.running} running · ${taskStats.pending} queued` : undefined, accent: liveTasks ? "var(--color-lime)" : undefined },
    { label: "Latest sync",  value: newestSync.value, sub: newestSync.sub },
  ]

  // Build the badge map — at-a-glance counts on the tabs themselves so admins
  // can spot e.g. "3 live tasks" without clicking into Activity.
  const tabBadges: Partial<Record<"users" | "system" | "activity" | "prompts", string | number>> = {
    users: users.length,
    activity: liveTasks ?? undefined,
  }

  return (
    <div style={{ padding: "0 0 32px" }}>
      <header style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
          Admin
        </div>
        <h1 style={{ margin: "4px 0 0", fontSize: 32, fontWeight: 400, letterSpacing: "-0.02em", color: "var(--color-text)", fontFamily: "var(--font-display-hero)" }}>
          Console
        </h1>
      </header>

      <StatStrip stats={stats} />

      <AdminTabs
        badges={tabBadges}
        panels={{
          users: usersPanel,
          system: (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
              <SystemCheck idToken={idToken} />
              {health?.syncs && Object.keys(health.syncs).length > 0 ? (
                <SyncPanel
                  initial={Object.entries(health.syncs).map(([source, infoRaw]) => {
                    const info = infoRaw as { status?: string; row_count?: number; last_synced_at?: string }
                    return { source, ...info }
                  })}
                  idToken={idToken}
                />
              ) : (
                <div style={{ padding: 16, fontSize: 12, color: "var(--color-text-faint)", border: "1px dashed var(--color-border)", borderRadius: 6 }}>
                  No sync sources reported by the API. The sync engine starts on
                  the next backend boot — re-run a sync trigger to seed.
                </div>
              )}
            </div>
          ),
          activity: (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
              <TasksPanel idToken={idToken} />
              <AuditLogPanel idToken={idToken} />
            </div>
          ),
          prompts: <PromptsPanel idToken={idToken} />,
          compliance: <ComplianceW9Panel idToken={idToken} />,
          integrations: <IntegrationsPanel idToken={idToken} />,
        }}
      />
    </div>
  )
}

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
