"use client"

import { useState } from "react"
import { api, type UserProfile, type UserUpdate } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"

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
}

export function UsersPanel({ users: initialUsers, error, idToken: serverToken }: UsersPanelProps) {
  const idToken = useIdToken(serverToken)
  const client = api(idToken ?? null)

  const [users, setUsers] = useState<UserProfile[]>(initialUsers)
  const [editingEmail, setEditingEmail] = useState<string | null>(null)
  const [editRole, setEditRole] = useState("")
  const [editTabs, setEditTabs] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState("")

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
    setSaving(true)
    setSaveMsg("")
    try {
      const allSelected = ALL_TABS.every((t) => editTabs.has(t))
      const body: UserUpdate = {
        role: editRole,
        allowed_tabs: allSelected ? "ALL" : Array.from(editTabs).join(", "),
      }
      const updated = await client.users.update(editingEmail, body)
      setUsers((prev) =>
        prev.map((u) => (u.email === editingEmail ? updated : u))
      )
      setSaveMsg("Saved")
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

  if (error) return <ErrorAlert>{error}</ErrorAlert>

  return (
    <div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {["Name", "Email", "Role", "Allowed Tabs", ""].map((h) => (
              <th
                key={h}
                className="text-left font-medium"
                style={{
                  fontSize: 11,
                  color: "var(--color-text-faint)",
                  padding: "6px 10px",
                  borderBottom: "1px solid var(--color-border)",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const isEditing = editingEmail === u.email
            return (
              <tr
                key={u.email}
                style={{
                  borderBottom: "1px solid var(--color-border)",
                  background: isEditing ? "var(--color-elevated)" : undefined,
                }}
              >
                <td style={{ padding: "8px 10px", fontSize: 13, color: "var(--color-text)", fontWeight: 500 }}>
                  {u.name}
                </td>
                <td style={{ padding: "8px 10px", fontSize: 12, color: "var(--color-text-muted)" }}>
                  {u.email}
                </td>
                <td style={{ padding: "8px 10px" }}>
                  {isEditing ? (
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value)}
                      style={{
                        background: "var(--color-base)",
                        color: "var(--color-text)",
                        border: "1px solid var(--color-border)",
                        borderRadius: 4,
                        padding: "3px 6px",
                        fontSize: 12,
                      }}
                    >
                      <option value="admin">admin</option>
                      <option value="editor">editor</option>
                    </select>
                  ) : (
                    <span
                      className="rounded px-2 py-0.5"
                      style={{
                        fontSize: 11,
                        fontWeight: 500,
                        background: u.role === "admin"
                          ? "color-mix(in srgb, var(--color-lime) 15%, transparent)"
                          : "color-mix(in srgb, var(--color-text-muted) 15%, transparent)",
                        color: u.role === "admin" ? "var(--color-lime)" : "var(--color-text-muted)",
                      }}
                    >
                      {u.role}
                    </span>
                  )}
                </td>
                <td style={{ padding: "8px 10px" }}>
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
                              : "var(--color-base)",
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
                      {u.allowed_tabs === "ALL" ? "All tabs" : u.allowed_tabs || "—"}
                    </span>
                  )}
                </td>
                <td style={{ padding: "8px 10px", textAlign: "right", whiteSpace: "nowrap" }}>
                  {isEditing ? (
                    <div className="flex items-center gap-2 justify-end">
                      {saveMsg && (
                        <span style={{ fontSize: 11, color: saveMsg === "Saved" ? "var(--color-ok)" : "var(--color-err)" }}>
                          {saveMsg}
                        </span>
                      )}
                      <button
                        onClick={cancelEdit}
                        className="rounded px-2 py-1 transition-colors hover:bg-[--color-base]"
                        style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={saveUser}
                        disabled={saving}
                        className="rounded px-3 py-1 font-medium transition-colors"
                        style={{
                          fontSize: 11,
                          background: "var(--color-lime)",
                          color: "#000",
                          opacity: saving ? 0.5 : 1,
                        }}
                      >
                        {saving ? "Saving..." : "Save"}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => startEdit(u)}
                      className="rounded px-2 py-1 transition-colors hover:bg-[--color-elevated]"
                      style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
