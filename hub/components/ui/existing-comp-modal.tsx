"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import { api, type ExistingComp } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"

const STATUSES = ["Draft", "Planned", "Published"] as const

/** Detail modal for a single existing compilation row. Lifts the scene grid
 *  + description + metadata out of the inline accordion so the Existing
 *  table stays a clean list, and the detail view has room to breathe.
 *
 *  Title / Volume / Status / Description are inline-editable — click the
 *  pencil to enter edit mode, save persists to the studio Index sheet via
 *  PATCH /api/compilations/{comp_id}. Scene-list editing is intentionally
 *  out of scope here (separate flow).
 */
export function ExistingCompModal({
  comp,
  studioColor,
  onClose,
  onDeleted,
  serverIdToken,
}: {
  comp: ExistingComp
  studioColor: string
  onClose: () => void
  /** Fired after a successful DELETE so the parent can drop the comp from
   *  its list without a full refetch. The modal closes itself. */
  onDeleted?: (compId: string) => void
  serverIdToken?: string
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  const idToken = useIdToken(serverIdToken)
  const client = api(idToken ?? null)

  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(comp.title)
  const [volume, setVolume] = useState(comp.volume)
  const [status, setStatus] = useState(comp.status || "Draft")
  const [description, setDescription] = useState(comp.description)
  const [saving, setSaving] = useState(false)
  const [saveErr, setSaveErr] = useState<string | null>(null)
  const [conflict, setConflict] = useState<{
    title: string
    volume: string
    status: string
    description: string
  } | null>(null)

  const [photosetOpen, setPhotosetOpen] = useState(false)
  // Two-stage destructive confirm — first click arms, second click commits.
  // Auto-disarms after 4s so a stale armed state doesn't surprise the user
  // when they come back to the modal later.
  const [armDelete, setArmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  useEffect(() => {
    if (!armDelete) return
    const t = setTimeout(() => setArmDelete(false), 4000)
    return () => clearTimeout(t)
  }, [armDelete])

  async function remove() {
    setDeleting(true)
    setSaveErr(null)
    try {
      await client.compilations.remove(comp.comp_id)
      onDeleted?.(comp.comp_id)
      onClose()
    } catch (e) {
      setSaveErr(e instanceof Error ? e.message : "Delete failed")
      setArmDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  // Stay in sync if the parent swaps the comp object (e.g. list refresh).
  useEffect(() => {
    setTitle(comp.title)
    setVolume(comp.volume)
    setStatus(comp.status || "Draft")
    setDescription(comp.description)
    setEditing(false)
    setSaveErr(null)
  }, [comp.comp_id, comp.title, comp.volume, comp.status, comp.description])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !editing) onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose, editing])

  if (!mounted) return null

  const stat = statusColors(status)
  const dirty =
    title !== comp.title ||
    volume !== comp.volume ||
    status !== (comp.status || "Draft") ||
    description !== comp.description

  async function save() {
    setSaving(true)
    setSaveErr(null)
    setConflict(null)
    try {
      await client.compilations.patch(comp.comp_id, {
        title,
        volume,
        status,
        description,
        // Snapshot of what the client thinks is on the server. Backend rejects
        // with 409 if any field has changed since this modal was opened.
        if_match: {
          title: comp.title,
          volume: comp.volume,
          status: comp.status || "Draft",
          description: comp.description,
        },
      })
      setEditing(false)
      // The parent's list won't auto-refresh; mutate the local comp object so
      // subsequent reopens show the new values until the user reloads.
      comp.title = title
      comp.volume = volume
      comp.status = status
      comp.description = description
    } catch (e) {
      // ApiError carries `status` + raw body string. For 409 the body is a
      // JSON-stringified `{detail: {message, current}}` from FastAPI's
      // HTTPException; surface the snapshot to the user.
      const status = (e as { status?: number })?.status
      const body = (e as { body?: string })?.body
      if (status === 409 && body) {
        try {
          const parsed = JSON.parse(body)
          const current = parsed?.detail?.current
          if (current) {
            setConflict(current)
            setSaveErr("Someone else edited this — review their changes below.")
            return
          }
        } catch {
          // Fall through to plain error
        }
      }
      setSaveErr(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  function acceptTheirChanges() {
    if (!conflict) return
    comp.title = conflict.title
    comp.volume = conflict.volume
    comp.status = conflict.status
    comp.description = conflict.description
    setTitle(conflict.title)
    setVolume(conflict.volume)
    setStatus(conflict.status || "Draft")
    setDescription(conflict.description)
    setConflict(null)
    setSaveErr(null)
  }

  function cancel() {
    setTitle(comp.title)
    setVolume(comp.volume)
    setStatus(comp.status || "Draft")
    setDescription(comp.description)
    setSaveErr(null)
    setEditing(false)
  }

  const photosetCmd = `python3 ~/Scripts/comp_photoset.py --comp-id ${comp.comp_id} --scenes ${comp.scenes.map(s => s.scene_id).join(",")} --output ~/Desktop/Compilations --zip`

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="comp-modal-title"
      onClick={() => !editing && onClose()}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "var(--color-backdrop)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fadeIn var(--duration-base) var(--ease-out-expo) both",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(720px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
          minHeight: 0,
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--color-border)",
            flexShrink: 0,
          }}
        >
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: studioColor,
                marginBottom: 6,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>{comp.comp_id}</span>
              {!editing ? (
                volume && <span style={{ color: "var(--color-text-faint)" }}>· {volume}</span>
              ) : (
                <input
                  value={volume}
                  onChange={e => setVolume(e.target.value)}
                  placeholder="Vol. 1 / New"
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.16em",
                    textTransform: "uppercase",
                    background: "var(--color-elevated)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                    padding: "2px 6px",
                    width: 110,
                    outline: "none",
                  }}
                />
              )}
            </div>
            {editing ? (
              <input
                id="comp-modal-title"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Title"
                style={{
                  fontFamily: "var(--font-display-hero)",
                  fontWeight: 400,
                  fontSize: 28,
                  lineHeight: 1.05,
                  letterSpacing: "-0.02em",
                  color: "var(--color-text)",
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border)",
                  padding: "4px 8px",
                  width: "100%",
                  outline: "none",
                }}
              />
            ) : (
              <h2
                id="comp-modal-title"
                style={{
                  fontFamily: "var(--font-display-hero)",
                  fontWeight: 400,
                  fontSize: 28,
                  lineHeight: 1.05,
                  letterSpacing: "-0.02em",
                  color: "var(--color-text)",
                  margin: 0,
                }}
              >
                {comp.title || <span style={{ color: "var(--color-text-faint)" }}>Untitled</span>}
              </h2>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
              {editing ? (
                <select
                  value={status}
                  onChange={e => setStatus(e.target.value)}
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    padding: "3px 6px",
                    color: stat.fg,
                    background: stat.bg,
                    border: `1px solid ${stat.border}`,
                    outline: "none",
                  }}
                >
                  {STATUSES.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              ) : (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    padding: "3px 8px",
                    color: stat.fg,
                    background: stat.bg,
                    border: `1px solid ${stat.border}`,
                  }}
                >
                  {comp.status || "Draft"}
                </span>
              )}
              <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                {comp.scene_count} scene{comp.scene_count === 1 ? "" : "s"}
              </span>
              {comp.created && (
                <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                  Created {comp.created}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 18, overflowY: "auto", flex: "1 1 auto", minHeight: 0 }}>
          {conflict && (
            <div
              role="alert"
              style={{
                padding: "12px 14px",
                background: "color-mix(in srgb, var(--color-warn, #f59e0b) 12%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-warn, #f59e0b) 35%, transparent)",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-warn, #f59e0b)" }}>
                Edit conflict
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text)" }}>
                Someone else saved changes to this compilation while you were editing.
                Their version is shown below — load it to start over, or keep editing
                to overwrite.
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: 11, color: "var(--color-text-muted)" }}>
                <span>Title</span><span style={{ color: "var(--color-text)" }}>{conflict.title || "—"}</span>
                <span>Volume</span><span style={{ color: "var(--color-text)" }}>{conflict.volume || "—"}</span>
                <span>Status</span><span style={{ color: "var(--color-text)" }}>{conflict.status || "—"}</span>
                <span>Desc</span><span style={{ color: "var(--color-text)", whiteSpace: "pre-wrap" }}>{conflict.description || "—"}</span>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                <button
                  type="button"
                  onClick={acceptTheirChanges}
                  style={{
                    fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
                    padding: "5px 12px", background: "var(--color-text)", color: "var(--color-base)",
                    border: "1px solid transparent", cursor: "pointer",
                  }}
                >
                  Load their version
                </button>
                <button
                  type="button"
                  onClick={() => {
                    // The user is explicitly choosing to overwrite. Adopt the
                    // server's current state as the if_match snapshot so the
                    // next save passes the optimistic check; the form's local
                    // values (their edits) are sent unchanged.
                    if (conflict) {
                      comp.title = conflict.title
                      comp.volume = conflict.volume
                      comp.status = conflict.status
                      comp.description = conflict.description
                    }
                    setConflict(null)
                    setSaveErr(null)
                  }}
                  style={{
                    fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
                    padding: "5px 12px", background: "transparent", color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)", cursor: "pointer",
                  }}
                >
                  Keep my edits
                </button>
              </div>
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <SectionLabel>Description</SectionLabel>
            {editing ? (
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                rows={5}
                placeholder="Compilation description"
                style={{
                  fontSize: 12.5,
                  color: "var(--color-text)",
                  lineHeight: 1.65,
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border)",
                  padding: "8px 10px",
                  resize: "vertical",
                  outline: "none",
                  fontFamily: "inherit",
                }}
              />
            ) : (
              comp.description
                ? <p style={{ fontSize: 12.5, color: "var(--color-text)", lineHeight: 1.65, whiteSpace: "pre-wrap", margin: 0 }}>{comp.description}</p>
                : <p style={{ fontSize: 12, color: "var(--color-text-faint)", margin: 0, fontStyle: "italic" }}>No description.</p>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <SectionLabel>Scenes</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {comp.scenes.map((sc) => (
                <div
                  key={`${comp.comp_id}-${sc.scene_num}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "28px auto 1fr auto auto",
                    alignItems: "center",
                    columnGap: 12,
                    padding: "8px 12px",
                    background: "var(--color-elevated)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--color-text-faint)",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {String(sc.scene_num).padStart(2, "0")}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      letterSpacing: "0.08em",
                      fontWeight: 700,
                      color: studioColor,
                    }}
                  >
                    {sc.scene_id}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--color-text)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {sc.title || <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                    {sc.performers || "—"}
                  </span>
                  {sc.mega_link ? (
                    <a
                      href={sc.mega_link}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: "0.1em",
                        textTransform: "uppercase",
                        color: studioColor,
                        textDecoration: "none",
                        padding: "2px 8px",
                        border: `1px solid color-mix(in srgb, ${studioColor} 35%, transparent)`,
                      }}
                    >
                      MEGA →
                    </a>
                  ) : (
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: "0.1em",
                        textTransform: "uppercase",
                        color: "var(--color-text-faint)",
                        padding: "2px 8px",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      Pending
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Photoset build helper — copy-paste command for the local Mac
              script. Mirrors the affordance in Builder mode but prefilled
              with this comp's real ID and scene IDs. */}
          <div>
            <SectionLabel>Photoset (Mac-local)</SectionLabel>
            <div style={{ marginTop: 6, border: "1px solid var(--color-border)", background: "var(--color-elevated)" }}>
              <button
                type="button"
                onClick={() => setPhotosetOpen(o => !o)}
                aria-expanded={photosetOpen}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  width: "100%",
                  padding: "8px 12px",
                  background: "transparent",
                  border: "none",
                  color: "var(--color-text-muted)",
                  fontSize: 11,
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <span aria-hidden style={{ fontSize: 9, color: "var(--color-text-faint)", transform: photosetOpen ? "rotate(90deg)" : undefined, transition: "transform 150ms" }}>▶</span>
                Build Photoset (rclone + Pillow)
                <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-text-faint)" }}>
                  {comp.scenes.length} scene{comp.scenes.length === 1 ? "" : "s"}
                </span>
              </button>
              {photosetOpen && (
                <div style={{ padding: "0 12px 12px", borderTop: "1px solid var(--color-border)" }}>
                  <pre
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--color-text)",
                      background: "var(--color-base)",
                      padding: "10px 12px",
                      margin: "10px 0 6px",
                      overflow: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                    }}
                  >{photosetCmd}</pre>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <p style={{ fontSize: 10, color: "var(--color-text-faint)", margin: 0 }}>
                      Run on your Mac. Requires rclone + Pillow.
                    </p>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard?.writeText(photosetCmd)}
                      style={{
                        fontSize: 10,
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        padding: "4px 10px",
                        background: "transparent",
                        color: "var(--color-text-muted)",
                        border: "1px solid var(--color-border)",
                        cursor: "pointer",
                      }}
                    >
                      Copy
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
            background: "var(--color-surface)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <span style={{ fontSize: 10, color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {comp.created_by ? `By ${comp.created_by}` : "—"}
              {comp.updated && comp.updated !== comp.created && ` · Updated ${comp.updated}`}
            </span>
            {!editing && (
              <button
                type="button"
                onClick={() => (armDelete ? remove() : setArmDelete(true))}
                disabled={deleting}
                aria-label={armDelete ? `Confirm delete ${comp.comp_id}` : `Delete ${comp.comp_id}`}
                style={{
                  padding: "5px 10px",
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  background: armDelete ? "var(--color-err)" : "transparent",
                  color: armDelete ? "var(--color-base)" : "var(--color-err)",
                  border: `1px solid ${armDelete ? "var(--color-err)" : "color-mix(in srgb, var(--color-err) 35%, transparent)"}`,
                  cursor: deleting ? "wait" : "pointer",
                  flexShrink: 0,
                }}
              >
                {deleting ? "Deleting…" : armDelete ? "Confirm delete" : "Delete"}
              </button>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {saveErr && (
              <span style={{ fontSize: 10, color: "var(--color-err)", letterSpacing: "0.04em" }}>
                {saveErr}
              </span>
            )}
            {editing ? (
              <>
                <button
                  type="button"
                  onClick={cancel}
                  disabled={saving}
                  style={{
                    padding: "6px 14px",
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    background: "transparent",
                    color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                    cursor: saving ? "wait" : "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={save}
                  disabled={saving || !dirty}
                  style={{
                    padding: "6px 14px",
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    background: "var(--color-lime)",
                    color: "var(--color-lime-ink)",
                    border: "1px solid transparent",
                    cursor: saving || !dirty ? "not-allowed" : "pointer",
                    opacity: !dirty ? 0.5 : 1,
                  }}
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  style={{
                    padding: "6px 14px",
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    background: "transparent",
                    color: "var(--color-text)",
                    border: "1px solid var(--color-border)",
                    cursor: "pointer",
                  }}
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  style={{
                    padding: "6px 14px",
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    background: "transparent",
                    color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                    cursor: "pointer",
                  }}
                >
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--color-text-faint)",
      }}
    >
      {children}
    </div>
  )
}

function statusColors(status: string) {
  const s = status.trim().toLowerCase()
  if (s === "published") return { fg: "var(--color-ok)", bg: "color-mix(in srgb, var(--color-ok) 12%, transparent)", border: "color-mix(in srgb, var(--color-ok) 30%, transparent)" }
  if (s === "planned")   return { fg: "var(--color-text)", bg: "var(--color-elevated)", border: "var(--color-border)" }
  return { fg: "var(--color-text-muted)", bg: "color-mix(in srgb, var(--color-text-muted) 10%, transparent)", border: "var(--color-border)" }
}
