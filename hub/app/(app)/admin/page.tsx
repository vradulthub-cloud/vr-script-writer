import { auth } from "@/auth"
import { api, type UserProfile } from "@/lib/api"
import { requireAdmin } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { UsersPanel } from "./users-panel"
import { SystemCheck } from "./system-check"

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

  const [usersRes, healthRes] = await Promise.allSettled([
    client.users.list(),
    v2 ? client.health() : Promise.resolve(null),
  ])
  if (usersRes.status === "fulfilled") users = usersRes.value
  else error = usersRes.reason instanceof Error ? usersRes.reason.message : "Failed to load users"
  if (v2 && healthRes.status === "fulfilled") health = healthRes.value

  const panel = <UsersPanel users={users} error={error} idToken={idToken} currentEmail={me.email} />
  if (!v2) return panel

  const activeCount = users.filter(u => u.role).length
  const adminCount = users.filter(u => (u.role ?? "").toLowerCase() === "admin").length
  const editorCount = users.filter(u => (u.role ?? "").toLowerCase() === "editor").length

  return (
    <div className="ec-cols">
      <div className="ec-col">{panel}</div>
      <div className="ec-col">
        <section className="ec-block ec-inverted">
          <header><h2>System</h2></header>
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
            <AdminStat label="Version" value={health?.version ?? "—"} mono />
            <AdminStat label="Status" value={health?.status ?? "—"} />
            <AdminStat label="Users" value={`${activeCount}`} sub={`${adminCount} admin · ${editorCount} editor`} />
          </div>
        </section>

        <SystemCheck idToken={idToken} />

        {health?.syncs && Object.keys(health.syncs).length > 0 && (
          <section className="ec-block">
            <header><h2>Syncs</h2></header>
            <ul className="ec-list">
              {Object.entries(health.syncs).map(([source, infoRaw]) => {
                const info = infoRaw as { status?: string; row_count?: number; last_synced_at?: string }
                const ok = !info.status || info.status === "ok" || info.status === "synced"
                return (
                  <li key={source} style={{ gridTemplateColumns: "10px 1fr auto" }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: ok ? "var(--color-ok)" : "var(--color-err)" }} />
                    <span style={{ fontSize: 12, color: "var(--color-text)" }}>{source}</span>
                    <span style={{ fontSize: 10, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums", letterSpacing: "0.1em", textTransform: "uppercase" }}>
                      {info.row_count !== undefined ? `${info.row_count.toLocaleString()} rows` : info.status ?? "—"}
                    </span>
                  </li>
                )
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
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
          fontSize: 28,
          letterSpacing: "-0.03em",
          fontFamily: mono ? "var(--font-mono)" : "var(--font-display-hero)",
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ marginTop: 2, fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(255,255,255,0.55)" }}>
          {sub}
        </div>
      )}
    </div>
  )
}
