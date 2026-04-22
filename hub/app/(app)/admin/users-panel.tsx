"use client"

import { useState, useMemo } from "react"
import { api, type UserProfile, type UserUpdate } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { PageHeader } from "@/components/ui/page-header"
import { Panel } from "@/components/ui/panel"
import { ConfirmModal } from "@/components/ui/confirm-modal"

const ALL_TABS = [
  "Tickets",
  "Model Research",
  "Scripts",
  "Call Sheets",
  "Titles",
  "Descriptions",
  "Compilations",
]

interface UsersPanelProps {
  users: UserProfile[]
  error: string | null
  idToken: string | undefined
  currentEmail: string
}

export function UsersPanel({ users: initialUsers, error, idToken: serverToken, currentEmail }: UsersPanelProps) {
  const idToken = useIdToken(serverToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [users, setUsers] = useState<UserProfile[]>(initialUsers)
  const [editingEmail, setEditingEmail] = useState<string | null>(null)
  const [editRole, setEditRole] = useState("")
  const [editTabs, setEditTabs] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState("")

  // Confirmation modal state — tracks which destructive action (if any) is
  // awaiting confirmation. Having it as a tagged union keeps one modal slot
  // for both remove-user and role-change prompts.
  type PendingConfirm =
    | { kind: "remove"; user: UserProfile; busy: boolean }
    | { kind: "role"; email: string; newRole: string; oldRole: string }
    | null
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm>(null)
  const [pendingSaveAfterRole, setPendingSaveAfterRole] = useState<null | (() => Promise<void>)>(null)

  // Add-user form state. Inline rather than a modal so admins see the
  // existing roster while typing — fewer mistakes (e.g. duplicate names).
  const [addOpen, setAddOpen] = useState(false)
  const [addEmail, setAddEmail] = useState("")
  const [addName, setAddName] = useState("")
  const [addRole, setAddRole] = useState("editor")
  const [addBusy, setAddBusy] = useState(false)
  const [addMsg, setAddMsg] = useState("")

  async function addUser() {
    const email = addEmail.trim().toLowerCase()
    const name = addName.trim()
    if (!email || !name) { setAddMsg("Email and name are required"); return }
    if (users.some(u => u.email.toLowerCase() === email)) {
      setAddMsg("That email is already in the roster"); return
    }
    setAddBusy(true)
    setAddMsg("")
    try {
      const created = await client.users.create({ email, name, role: addRole, allowed_tabs: "ALL" })
      setUsers(prev => [...prev, created])
      setAddEmail(""); setAddName(""); setAddRole("editor")
      setAddOpen(false)
    } catch (e) {
      setAddMsg(e instanceof Error ? e.message : "Failed to add user")
    } finally {
      setAddBusy(false)
    }
  }

  function removeUser(u: UserProfile) {
    const isSelf = u.email.toLowerCase() === (currentEmail ?? "").toLowerCase()
    if (isSelf) { window.alert("You can't remove yourself."); return }
    setPendingConfirm({ kind: "remove", user: u, busy: false })
  }

  async function doRemoveUser(u: UserProfile) {
    setPendingConfirm(prev => prev && prev.kind === "remove" ? { ...prev, busy: true } : prev)
    try {
      await client.users.remove(u.email)
      setUsers(prev => prev.filter(x => x.email !== u.email))
      setPendingConfirm(null)
    } catch (e) {
      setPendingConfirm(null)
      window.alert(e instanceof Error ? e.message : "Failed to remove user")
    }
  }

  function startEdit(user: UserProfile) {
    setEditingEmail(user.email)
    setEditRole(user.role)
    const tabs = user.allowed_tabs === "ALL" || !user.allowed_tabs
      ? new Set(ALL_TABS)
      : new Set(user.allowed_tabs.split(",").map((t) => t.trim()).filter(Boolean))
    setEditTabs(tabs)
    setSaveMsg("")
  }

  function cancelEdit() {
    setEditingEmail(null)
    setSaveMsg("")
  }

  function toggleTab(tab: string) {
    setEditTabs((prev) => {
      const next = new Set(prev)
      if (next.has(tab)) next.delete(tab)
      else next.add(tab)
      return next
    })
  }

  async function saveUser() {
    if (!editingEmail) return
    // Self-lockout guard — block the only changes that would revoke the
    // signed-in admin's own access. Another admin can still do it for them.
    const isSelf = editingEmail.toLowerCase() === (currentEmail ?? "").toLowerCase()
    if (isSelf && editRole !== "admin") {
      setSaveMsg("You can't remove your own admin role. Ask another admin.")
      return
    }
    if (isSelf && editTabs.size === 0) {
      setSaveMsg("You can't clear your own tabs — you'd lock yourself out.")
      return
    }
    const allSelected = ALL_TABS.every((t) => editTabs.has(t))
    const nextTabs = allSelected ? "ALL" : Array.from(editTabs).join(", ")
    const previous = users.find((u) => u.email === editingEmail)
    const prevRole = previous?.role ?? ""
    const prevTabs = previous?.allowed_tabs ?? ""
    const roleChanged = editRole !== prevRole
    const tabsChanged = nextTabs !== prevTabs

    if (!roleChanged && !tabsChanged) {
      setSaveMsg("No changes.")
      return
    }

    // Role changes are privileged — require explicit confirmation so a
    // slip-of-the-finger doesn't promote an editor to admin. Modal replaces
    // the old window.confirm so the change is framed in context.
    const doSave = async () => {
      setPendingConfirm(null)
      setPendingSaveAfterRole(null)
      await runSave()
    }
    if (roleChanged) {
      setPendingConfirm({ kind: "role", email: editingEmail, newRole: editRole, oldRole: prevRole })
      setPendingSaveAfterRole(() => doSave)
      return
    }
    await runSave()

    async function runSave() {
    setSaving(true)
    setSaveMsg("")
    try {
      const body: UserUpdate = { role: editRole, allowed_tabs: nextTabs }
      const updated = await client.users.update(editingEmail!, body)
      setUsers((prev) =>
        prev.map((u) => (u.email === editingEmail ? updated : u))
      )
      setSaveMsg("Saved")

      // Audit trail — log every permission change as a Hub ticket. The
      // tickets sheet is the closest thing we have to an audit log (users
      // sheet has no audit column, no dedicated endpoint exists). Swallow
      // failures so the audit log never blocks the save.
      const changes: string[] = []
      if (roleChanged) changes.push(`role ${prevRole || "(none)"} → ${editRole}`)
      if (tabsChanged) changes.push(`tabs ${prevTabs || "(none)"} → ${nextTabs}`)
      void client.tickets.create({
        title: `Admin change: ${editingEmail} — ${changes.join("; ")}`,
        description: `Changed by ${currentEmail || "unknown admin"} at ${new Date().toISOString()}.\n\n${changes.join("\n")}`,
        project: "Hub",
        type: "Audit",
        priority: "Low",
      }).catch((err) => {
        console.warn("[admin] audit log failed:", err)
      })

      setTimeout(() => {
        setEditingEmail(null)
        setSaveMsg("")
      }, 1200)
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
    }
  }

  if (error) return <ErrorAlert>{error}</ErrorAlert>

  const admins = users.filter(u => u.role === "admin").length

  return (
    <div>
      <PageHeader
        title="User Permissions"
        eyebrow="Admin"
        subtitle={`${users.length} user${users.length === 1 ? "" : "s"} · ${admins} admin · role + tab access control`}
        actions={
          <button
            type="button"
            onClick={() => setAddOpen(o => !o)}
            style={{
              background: addOpen ? "transparent" : "var(--color-lime)",
              color: addOpen ? "var(--color-text-muted)" : "var(--color-lime-ink, #0d0d0d)",
              border: addOpen ? "1px solid var(--color-border)" : "1px solid var(--color-lime)",
              padding: "6px 12px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              cursor: "pointer",
            }}
          >
            {addOpen ? "Cancel" : "+ Add user"}
          </button>
        }
      />
      {addOpen && (
        <Panel>
          <div style={{ padding: 14, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: "2 1 240px" }}>
              <span style={addLabelStyle}>Email</span>
              <input
                type="email"
                value={addEmail}
                onChange={e => setAddEmail(e.target.value)}
                placeholder="alex@eclatech.test"
                style={addInputStyle}
                autoFocus
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: "1 1 160px" }}>
              <span style={addLabelStyle}>Name</span>
              <input
                value={addName}
                onChange={e => setAddName(e.target.value)}
                placeholder="Alex Rivera"
                style={addInputStyle}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={addLabelStyle}>Role</span>
              <select
                value={addRole}
                onChange={e => setAddRole(e.target.value)}
                style={addInputStyle}
              >
                <option value="editor">editor</option>
                <option value="admin">admin</option>
              </select>
            </label>
            <button
              type="button"
              onClick={addUser}
              disabled={addBusy}
              style={{
                background: "var(--color-lime)",
                color: "var(--color-lime-ink, #0d0d0d)",
                border: "1px solid var(--color-lime)",
                padding: "6px 14px",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                cursor: addBusy ? "wait" : "pointer",
                opacity: addBusy ? 0.6 : 1,
                height: 30,
              }}
            >
              {addBusy ? "Saving…" : "Add"}
            </button>
            {addMsg && (
              <span role="status" style={{ fontSize: 11, color: "var(--color-err)" }}>{addMsg}</span>
            )}
          </div>
        </Panel>
      )}
      <Panel>
        <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
            {["Name", "Email", "Role", "Allowed Tabs", ""].map((h) => (
              <th
                key={h}
                scope="col"
                className="text-left px-3 py-2 font-medium"
                style={{ fontSize: 11, color: "var(--color-text-muted)" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const isEditing = editingEmail === u.email
            const isSelf = u.email.toLowerCase() === (currentEmail ?? "").toLowerCase()
            return (
              <tr
                key={u.email}
                style={{
                  borderBottom: "1px solid var(--color-border-subtle)",
                  background: isEditing ? "var(--color-surface)" : undefined,
                }}
              >
                <td className="px-3 py-2.5" style={{ fontSize: 13, color: "var(--color-text)", fontWeight: 500 }}>
                  {u.name}
                </td>
                <td className="px-3 py-2.5" style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  {u.email}
                </td>
                <td className="px-3 py-2.5">
                  {isEditing ? (
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value)}
                      disabled={isSelf}
                      title={isSelf ? "Another admin must change your role" : undefined}
                      className="px-2 py-1 rounded text-xs"
                      style={{ background: "var(--color-elevated)", color: "var(--color-text)", border: "1px solid var(--color-border)", opacity: isSelf ? 0.5 : 1, cursor: isSelf ? "not-allowed" : "pointer" }}
                    >
                      <option value="admin">admin</option>
                      <option value="editor">editor</option>
                    </select>
                  ) : (
                    <span
                      className="rounded px-2 py-0.5"
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                        background: "transparent",
                        border: `1px solid ${u.role === "admin" ? "color-mix(in srgb, var(--color-text) 40%, transparent)" : "var(--color-border)"}`,
                        color: u.role === "admin" ? "var(--color-text)" : "var(--color-text-muted)",
                      }}
                    >
                      {u.role}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {isEditing ? (
                    <div className="flex flex-wrap gap-1.5">
                      {ALL_TABS.map((tab) => (
                        <button
                          key={tab}
                          onClick={() => toggleTab(tab)}
                          className="rounded px-2 py-0.5 transition-colors"
                          style={{
                            fontSize: 10,
                            fontWeight: 500,
                            background: editTabs.has(tab)
                              ? "color-mix(in srgb, var(--color-lime) 20%, transparent)"
                              : "var(--color-elevated)",
                            color: editTabs.has(tab) ? "var(--color-lime)" : "var(--color-text-faint)",
                            border: `1px solid ${editTabs.has(tab) ? "color-mix(in srgb, var(--color-lime) 35%, transparent)" : "var(--color-border)"}`,
                          }}
                        >
                          {tab}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                      {u.allowed_tabs === "ALL" && u.role !== "admin" ? (
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          padding: "1px 6px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                          background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                          color: "var(--color-lime)",
                          border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                          letterSpacing: "0.04em",
                        }}>
                          Full access
                        </span>
                      ) : (
                        u.allowed_tabs === "ALL" ? "All tabs" : u.allowed_tabs || "—"
                      )}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {isEditing ? (
                    <div className="flex items-center gap-2 justify-end">
                      {saveMsg && (
                        <span role="status" aria-live="polite" style={{ fontSize: 11, color: saveMsg === "Saved" ? "var(--color-ok)" : "var(--color-err)" }}>
                          {saveMsg}
                        </span>
                      )}
                      <button
                        onClick={cancelEdit}
                        className="rounded px-2 py-1 transition-colors hover:bg-[--color-elevated]"
                        style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={saveUser}
                        disabled={saving}
                        className="rounded px-3 py-1 font-medium transition-colors"
                        style={{ fontSize: 11, background: "var(--color-lime)", color: "var(--color-base)", opacity: saving ? 0.5 : 1 }}
                      >
                        {saving ? "Saving…" : "Save"}
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => startEdit(u)}
                        className="rounded px-2 py-1 transition-colors hover:bg-[--color-elevated]"
                        style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                      >
                        Edit
                      </button>
                      {!isSelf && (
                        <button
                          onClick={() => removeUser(u)}
                          title={`Remove ${u.name}`}
                          className="rounded px-2 py-1 transition-colors hover:bg-[--color-elevated]"
                          style={{ fontSize: 11, color: "var(--color-err)" }}
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </Panel>

      {pendingConfirm?.kind === "remove" && (
        <ConfirmModal
          eyebrow="Destructive · Remove user"
          title={`Remove ${pendingConfirm.user.name}?`}
          tone="danger"
          confirmLabel="Remove user"
          busy={pendingConfirm.busy}
          onConfirm={() => doRemoveUser(pendingConfirm.user)}
          onCancel={() => setPendingConfirm(null)}
        >
          <p style={{ margin: 0 }}>
            <span style={{ color: "var(--color-text-muted)" }}>{pendingConfirm.user.email}</span>
            {" "}will lose access immediately.
          </p>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: "var(--color-text-muted)" }}>
            You can re-invite them later from this panel.
          </p>
        </ConfirmModal>
      )}

      {pendingConfirm?.kind === "role" && (
        <ConfirmModal
          eyebrow={pendingConfirm.newRole === "admin" ? "Privilege · Promote" : "Privilege · Downgrade"}
          title={pendingConfirm.newRole === "admin" ? "Promote to admin?" : `Downgrade to ${pendingConfirm.newRole}?`}
          tone="warn"
          confirmLabel={pendingConfirm.newRole === "admin" ? "Promote" : "Downgrade"}
          onConfirm={() => pendingSaveAfterRole?.()}
          onCancel={() => { setPendingConfirm(null); setPendingSaveAfterRole(null) }}
        >
          <p style={{ margin: 0 }}>
            <span style={{ color: "var(--color-text-muted)" }}>{pendingConfirm.email}</span>
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--color-text-muted)" }}>
            Role <span style={{ fontFamily: "var(--font-mono)" }}>{pendingConfirm.oldRole || "(none)"}</span>
            {" → "}
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text)" }}>{pendingConfirm.newRole}</span>
          </p>
          <p style={{ margin: "10px 0 0", fontSize: 11, color: "var(--color-text-faint)" }}>
            Logged in the tickets sheet as an audit entry.
          </p>
        </ConfirmModal>
      )}
    </div>
  )
}

const addLabelStyle: React.CSSProperties = {
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: "var(--color-text-muted)",
}

const addInputStyle: React.CSSProperties = {
  background: "var(--color-elevated)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text)",
  fontSize: 13,
  padding: "6px 10px",
  outline: "none",
  fontFamily: "inherit",
  height: 30,
}
