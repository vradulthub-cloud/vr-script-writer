"use client"

/**
 * SignatureEditModal — admin-only modal for correcting a compliance_signatures
 * row after the fact (typo in address, name change, etc.) without re-signing.
 *
 * Server is the source of truth for the audit trail: every PATCH writes the
 * prior state to compliance_signatures_history via the `trg_compliance_history`
 * trigger. We surface that history at the bottom of the modal so the operator
 * can see what changed and when.
 */
import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import { api, type SignatureRow, type SignatureHistoryEntry } from "@/lib/api"

const FIELDS: Array<{ key: keyof SignatureRow; label: string; multi?: boolean }> = [
  { key: "talent_display",  label: "Display name" },
  { key: "legal_name",      label: "Legal name" },
  { key: "business_name",   label: "Business / DBA name" },
  { key: "tax_classification", label: "Tax classification" },
  { key: "tin_type",        label: "TIN type (ssn / ein)" },
  { key: "tin",             label: "TIN" },
  { key: "dob",             label: "Date of birth (YYYY-MM-DD)" },
  { key: "place_of_birth",  label: "Place of birth" },
  { key: "street_address",  label: "Street address", multi: true },
  { key: "city_state_zip",  label: "City, state, ZIP" },
  { key: "phone",           label: "Phone" },
  { key: "email",           label: "Email" },
  { key: "id1_type",        label: "ID 1 type" },
  { key: "id1_number",      label: "ID 1 number" },
  { key: "id2_type",        label: "ID 2 type" },
  { key: "id2_number",      label: "ID 2 number" },
  { key: "stage_names",     label: "Stage / professional names", multi: true },
]


export function SignatureEditModal({
  signatureId,
  idToken,
  onClose,
  onSaved,
}: {
  signatureId: number
  idToken: string | undefined
  onClose: () => void
  onSaved?: () => void
}) {
  const client = api(idToken ?? null)
  const [row, setRow] = useState<SignatureRow | null>(null)
  const [history, setHistory] = useState<SignatureHistoryEntry[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [draft, setDraft] = useState<Partial<SignatureRow>>({})
  const [reason, setReason] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([
      client.compliance.getSignature(signatureId),
      client.compliance.signatureHistory(signatureId).catch(() => []),
    ])
      .then(([sig, hist]) => {
        if (cancelled) return
        setRow(sig)
        setHistory(hist)
        setDraft({})
      })
      .catch((e) => {
        if (cancelled) return
        setLoadError(e instanceof Error ? e.message : "Failed to load signature")
      })
    return () => { cancelled = true }
  }, [signatureId, client.compliance])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  function setField(key: keyof SignatureRow, value: string) {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  async function save() {
    if (!row) return
    // Only send fields that actually changed.
    const changes: Record<string, string> = {}
    for (const k of Object.keys(draft) as Array<keyof SignatureRow>) {
      const newVal = String(draft[k] ?? "")
      const oldVal = String(row[k] ?? "")
      if (newVal !== oldVal) changes[k] = newVal
    }
    if (Object.keys(changes).length === 0) {
      setSaveError("No changes to save.")
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await client.compliance.editSignature(signatureId, changes, reason)
      setRow(updated)
      setDraft({})
      setReason("")
      // Refresh history to reflect the new snapshot the trigger just wrote.
      const hist = await client.compliance.signatureHistory(signatureId).catch(() => [])
      setHistory(hist)
      onSaved?.()
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  function effectiveValue(k: keyof SignatureRow): string {
    if (k in draft) return String(draft[k] ?? "")
    return String(row?.[k] ?? "")
  }

  function dirtyCount(): number {
    if (!row) return 0
    let n = 0
    for (const k of Object.keys(draft) as Array<keyof SignatureRow>) {
      const newVal = String(draft[k] ?? "")
      const oldVal = String(row[k] ?? "")
      if (newVal !== oldVal) n++
    }
    return n
  }

  const body = (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit signature record"
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.65)",
        display: "flex", alignItems: "stretch", justifyContent: "center",
        padding: "32px 16px", overflowY: "auto",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-base)",
          border: "1px solid var(--color-border)",
          borderRadius: 12,
          width: "min(100%, 720px)",
          maxHeight: "calc(100vh - 64px)",
          display: "flex", flexDirection: "column",
        }}
      >
        <header style={{
          padding: "16px 20px", borderBottom: "1px solid var(--color-border)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <div style={{
              fontSize: 10.5, fontWeight: 700, letterSpacing: "0.14em",
              textTransform: "uppercase", color: "var(--color-text-faint)",
            }}>Edit signature</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", marginTop: 2 }}>
              {row?.talent_display ?? "—"}
              <span style={{
                marginLeft: 8, fontSize: 11, fontWeight: 500,
                color: "var(--color-text-faint)",
              }}>
                {row?.shoot_date} · {row?.talent_role}
              </span>
            </div>
          </div>
          <button
            type="button" onClick={onClose} aria-label="Close"
            style={{
              background: "transparent", border: "none", color: "var(--color-text-muted)",
              cursor: "pointer", padding: 6, display: "flex",
            }}
          ><X size={18} /></button>
        </header>

        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {loadError && (
            <div style={{ color: "var(--color-err)", fontSize: 13, marginBottom: 12 }}>
              {loadError}
            </div>
          )}
          {!row && !loadError && (
            <div style={{ color: "var(--color-text-faint)", fontSize: 13 }}>Loading…</div>
          )}

          {row && (
            <>
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr",
                gap: "12px 14px", fontSize: 12.5,
              }}>
                {FIELDS.map((f) => {
                  const value = effectiveValue(f.key)
                  const dirty = f.key in draft && String(draft[f.key] ?? "") !== String(row[f.key] ?? "")
                  return (
                    <label
                      key={f.key as string}
                      style={{
                        display: "flex", flexDirection: "column", gap: 4,
                        gridColumn: f.multi ? "1 / -1" : undefined,
                      }}
                    >
                      <span style={{
                        fontSize: 10.5, fontWeight: 600, letterSpacing: "0.07em",
                        textTransform: "uppercase",
                        color: dirty ? "var(--color-lime)" : "var(--color-text-muted)",
                      }}>
                        {f.label}{dirty && " ·"}
                      </span>
                      <input
                        type="text"
                        value={value}
                        onChange={(e) => setField(f.key, e.target.value)}
                        style={{
                          background: "var(--color-surface)",
                          border: `1px solid ${dirty ? "color-mix(in srgb, var(--color-lime) 40%, transparent)" : "var(--color-border)"}`,
                          borderRadius: 6, padding: "7px 9px", fontSize: 13,
                          color: "var(--color-text)", fontFamily: "inherit",
                        }}
                      />
                    </label>
                  )
                })}
              </div>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 16 }}>
                <span style={{
                  fontSize: 10.5, fontWeight: 600, letterSpacing: "0.07em",
                  textTransform: "uppercase", color: "var(--color-text-muted)",
                }}>
                  Reason (optional, recorded in audit trail)
                </span>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Updated address per email from talent"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 6, padding: "7px 9px", fontSize: 13,
                    color: "var(--color-text)", fontFamily: "inherit",
                  }}
                />
              </label>

              {saveError && (
                <div style={{ color: "var(--color-err)", fontSize: 12, marginTop: 10 }}>
                  {saveError}
                </div>
              )}

              {/* History */}
              <div style={{ marginTop: 24 }}>
                <div style={{
                  fontSize: 10.5, fontWeight: 700, letterSpacing: "0.14em",
                  textTransform: "uppercase", color: "var(--color-text-muted)",
                  marginBottom: 8,
                }}>
                  History · {history.length} prior version{history.length === 1 ? "" : "s"}
                </div>
                {history.length === 0 ? (
                  <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>
                    No edits yet — current row IS the original state.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {history.map((h) => (
                      <div
                        key={h.history_id}
                        style={{
                          background: "var(--color-surface)",
                          border: "1px solid var(--color-border-subtle)",
                          borderRadius: 6, padding: "8px 10px",
                          fontSize: 11.5, color: "var(--color-text-muted)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                          <span style={{ color: "var(--color-text)" }}>
                            {new Date(h.snapshot_at).toLocaleString()}
                          </span>
                          {h.edited_by && (
                            <span style={{ color: "var(--color-text-faint)" }}>{h.edited_by}</span>
                          )}
                        </div>
                        {h.edit_reason && (
                          <div style={{ marginTop: 3, fontStyle: "italic" }}>{h.edit_reason}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <footer style={{
          padding: "12px 20px", borderTop: "1px solid var(--color-border)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          <span style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
            {dirtyCount() > 0 ? `${dirtyCount()} field${dirtyCount() === 1 ? "" : "s"} changed` : "No changes"}
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                border: "1px solid var(--color-border)",
                borderRadius: 6, padding: "7px 14px",
                fontSize: 13, color: "var(--color-text-muted)",
                cursor: "pointer", fontFamily: "inherit",
              }}
            >Cancel</button>
            <button
              type="button"
              onClick={save}
              disabled={saving || dirtyCount() === 0}
              style={{
                background: dirtyCount() > 0 ? "var(--color-lime)" : "var(--color-elevated)",
                border: "none",
                borderRadius: 6, padding: "7px 18px",
                fontSize: 13, fontWeight: 600,
                color: dirtyCount() > 0 ? "#000" : "var(--color-text-faint)",
                cursor: saving ? "wait" : (dirtyCount() > 0 ? "pointer" : "not-allowed"),
                fontFamily: "inherit",
              }}
            >{saving ? "Saving…" : "Save changes"}</button>
          </div>
        </footer>
      </div>
    </div>
  )

  if (!mounted) return null
  return createPortal(body, document.body)
}
