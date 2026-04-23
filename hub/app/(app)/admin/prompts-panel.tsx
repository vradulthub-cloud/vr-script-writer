"use client"

import { useEffect, useMemo, useState, useCallback } from "react"
import { api, type PromptEntry } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { ErrorAlert } from "@/components/ui/error-alert"
import { ConfirmModal } from "@/components/ui/confirm-modal"

/**
 * AI Prompts editor.
 *
 * Lists every editable prompt (title gen / description gen / compilation
 * desc / script system prompt), grouped by surface. Selecting one opens a
 * full-height textarea editor with Save and Revert-to-default actions.
 *
 * Why this UI shape: the prompt strings are long (some 4+ KB) so a list +
 * editor pattern beats inline expand-collapse — the editor gets the room
 * it needs without making the list unscannable. Selection state is local;
 * each save round-trips to the API and updates the row in place.
 */
export function PromptsPanel({ idToken: serverIdToken }: { idToken?: string }) {
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [rows, setRows] = useState<PromptEntry[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [draft, setDraft] = useState<string>("")
  const [busy, setBusy] = useState(false)
  const [statusMsg, setStatusMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null)
  const [revertOpen, setRevertOpen] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const list = await client.prompts.list()
      setRows(list)
      setErr(null)
      // Preserve selection if the key still exists; otherwise pick the first.
      if (list.length > 0) {
        const stillThere = selectedKey && list.find(p => p.key === selectedKey)
        if (!stillThere) {
          setSelectedKey(list[0].key)
          setDraft(list[0].content)
        } else if (stillThere && draft === "") {
          setDraft(stillThere.content)
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load prompts")
    }
    // intentionally not depending on selectedKey/draft — refresh runs on mount
    // and after saves; we don't want it to re-fire when the user picks a row.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client])

  useEffect(() => { refresh() }, [refresh])

  // Group by `group` while preserving the registry order from the backend.
  const groups = useMemo(() => {
    const out: Record<string, PromptEntry[]> = {}
    if (!rows) return out
    const order: string[] = []
    for (const r of rows) {
      if (!out[r.group]) { out[r.group] = []; order.push(r.group) }
      out[r.group].push(r)
    }
    return order.reduce<Record<string, PromptEntry[]>>((acc, g) => { acc[g] = out[g]; return acc }, {})
  }, [rows])

  const selected = rows?.find(r => r.key === selectedKey) ?? null
  const isDirty = !!selected && draft !== selected.content

  function selectRow(p: PromptEntry) {
    if (isDirty && !window.confirm("Discard unsaved changes?")) return
    setSelectedKey(p.key)
    setDraft(p.content)
    setStatusMsg(null)
  }

  async function save() {
    if (!selected) return
    if (!draft.trim()) { setStatusMsg({ kind: "err", text: "Prompt can't be empty" }); return }
    setBusy(true)
    setStatusMsg(null)
    try {
      const updated = await client.prompts.save(selected.key, draft)
      setRows(prev => (prev ?? []).map(r => r.key === updated.key ? updated : r))
      setStatusMsg({ kind: "ok", text: "Saved · live on next generation" })
    } catch (e) {
      setStatusMsg({ kind: "err", text: e instanceof Error ? e.message : "Save failed" })
    } finally {
      setBusy(false)
    }
  }

  function revert() {
    if (!selected) return
    setRevertOpen(true)
  }

  async function doRevert() {
    if (!selected) return
    setBusy(true)
    setStatusMsg(null)
    setRevertOpen(false)
    try {
      await client.prompts.revert(selected.key)
      // Optimistically update locally — backend response is 204.
      const reset: PromptEntry = {
        ...selected,
        content: selected.default,
        is_overridden: false,
        updated_by: "",
        updated_at: "",
      }
      setRows(prev => (prev ?? []).map(r => r.key === reset.key ? reset : r))
      setDraft(reset.content)
      setStatusMsg({ kind: "ok", text: "Reverted to default" })
    } catch (e) {
      setStatusMsg({ kind: "err", text: e instanceof Error ? e.message : "Revert failed" })
    } finally {
      setBusy(false)
    }
  }

  if (err) return <ErrorAlert>{err}</ErrorAlert>
  if (!rows) return <div style={{ padding: 14, fontSize: 12, color: "var(--color-text-faint)" }}>Loading prompts…</div>

  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 16, alignItems: "stretch", minHeight: 500 }}>
      {/* ── Left: grouped list ──────────────────────────────────────── */}
      <aside
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          background: "var(--color-surface)",
          overflow: "auto",
          maxHeight: 720,
        }}
      >
        {Object.entries(groups).map(([groupName, items]) => (
          <div key={groupName}>
            <div
              style={{
                padding: "10px 12px 6px",
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--color-text-muted)",
                borderBottom: "1px solid var(--color-border-subtle)",
              }}
            >
              {groupName}
            </div>
            {items.map(p => {
              const isActive = p.key === selectedKey
              return (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => selectRow(p)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                    padding: "7px 12px",
                    background: isActive ? "color-mix(in srgb, var(--color-lime) 10%, transparent)" : "transparent",
                    border: "1px solid transparent",
                    outline: isActive ? "1px solid color-mix(in srgb, var(--color-lime) 25%, transparent)" : "none",
                    outlineOffset: -1,
                    borderRadius: 4,
                    color: isActive ? "var(--color-text)" : "var(--color-text-muted)",
                    fontSize: 12,
                    fontWeight: isActive ? 600 : 500,
                    cursor: "pointer",
                    textAlign: "left",
                    fontFamily: "inherit",
                  }}
                >
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {p.label.replace(/^[^—]+—\s*/, "")}
                  </span>
                  {p.is_overridden && (
                    <span
                      title={`Edited${p.updated_by ? ` by ${p.updated_by}` : ""}`}
                      style={{
                        width: 6, height: 6, borderRadius: "50%",
                        background: "var(--color-lime)",
                        marginLeft: 8,
                        flexShrink: 0,
                      }}
                    />
                  )}
                </button>
              )
            })}
          </div>
        ))}
      </aside>

      {/* ── Right: editor ───────────────────────────────────────────── */}
      <section
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          minWidth: 0,
        }}
      >
        {!selected ? (
          <div style={{ padding: 24, color: "var(--color-text-faint)", fontSize: 12 }}>
            Select a prompt on the left to edit it.
          </div>
        ) : (
          <>
            <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
              <div>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-muted)" }}>
                  {selected.group}
                </div>
                <h3 style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em", color: "var(--color-text)" }}>
                  {selected.label}
                </h3>
                <code style={{ fontSize: 11, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
                  key: {selected.key}
                </code>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {selected.is_overridden && (
                  <span
                    style={{
                      fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
                      padding: "2px 7px", borderRadius: 3,
                      background: "color-mix(in srgb, var(--color-lime) 14%, transparent)",
                      color: "var(--color-lime)",
                      border: "1px solid color-mix(in srgb, var(--color-lime) 30%, transparent)",
                    }}
                  >
                    Edited
                  </span>
                )}
                {selected.updated_at && (
                  <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                    {selected.updated_by} · {new Date(selected.updated_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
            </header>

            <textarea
              value={draft}
              onChange={e => setDraft(e.target.value)}
              spellCheck={false}
              style={{
                flex: 1,
                minHeight: 480,
                width: "100%",
                background: "var(--color-elevated)",
                color: "var(--color-text)",
                border: `1px solid ${isDirty ? "color-mix(in srgb, var(--color-lime) 50%, var(--color-border))" : "var(--color-border)"}`,
                borderRadius: 6,
                padding: 14,
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                lineHeight: 1.55,
                resize: "vertical",
                outline: "none",
                tabSize: 2,
              }}
            />

            <footer style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                {draft.length.toLocaleString()} chars · {wordCount(draft).toLocaleString()} words
                {isDirty && <span style={{ marginLeft: 8, color: "var(--color-lime)", fontWeight: 600 }}>● unsaved</span>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {statusMsg && (
                  <span
                    role="status"
                    style={{
                      fontSize: 11, fontWeight: 600,
                      color: statusMsg.kind === "ok" ? "var(--color-ok)" : "var(--color-err)",
                    }}
                  >
                    {statusMsg.text}
                  </span>
                )}
                <button
                  type="button"
                  onClick={revert}
                  disabled={busy || !selected.is_overridden}
                  title={selected.is_overridden ? "Revert to bundled default" : "No override to revert"}
                  style={{
                    background: "transparent",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text-muted)",
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    padding: "6px 12px",
                    borderRadius: 4,
                    cursor: busy || !selected.is_overridden ? "not-allowed" : "pointer",
                    opacity: busy || !selected.is_overridden ? 0.5 : 1,
                  }}
                >
                  Revert to default
                </button>
                <button
                  type="button"
                  onClick={save}
                  disabled={busy || !isDirty}
                  style={{
                    background: isDirty ? "var(--color-lime)" : "transparent",
                    border: `1px solid ${isDirty ? "var(--color-lime)" : "var(--color-border)"}`,
                    color: isDirty ? "var(--color-lime-ink, #0d0d0d)" : "var(--color-text-faint)",
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    padding: "6px 14px",
                    borderRadius: 4,
                    cursor: busy || !isDirty ? "not-allowed" : "pointer",
                    opacity: busy ? 0.6 : 1,
                  }}
                >
                  {busy ? "Saving…" : "Save"}
                </button>
              </div>
            </footer>
          </>
        )}
      </section>

      {revertOpen && selected && (
        <ConfirmModal
          eyebrow="Revert · bundled default"
          title={`Revert "${selected.label}"?`}
          tone="warn"
          confirmLabel="Revert to default"
          busy={busy}
          onConfirm={doRevert}
          onCancel={() => setRevertOpen(false)}
        >
          <p style={{ margin: 0 }}>
            Your custom version will be discarded and replaced with the prompt that shipped with the app.
          </p>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: "var(--color-text-muted)" }}>
            You can re-customize it afterwards — the default isn't locked.
          </p>
        </ConfirmModal>
      )}
    </div>
  )
}

function wordCount(s: string): number {
  const m = s.trim().match(/\S+/g)
  return m ? m.length : 0
}
