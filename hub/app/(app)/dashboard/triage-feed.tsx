"use client"

import { useState, useCallback, useRef } from "react"
import Link from "next/link"
import { X } from "lucide-react"
import { api, type Approval, type Scene, type Script } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { STUDIO_COLOR, STUDIO_ABBR } from "@/lib/studio-colors"

const CONTENT_TYPE_LABEL: Record<string, string> = {
  description: "Description",
  script:      "Script",
  compilation: "Compilation",
}

const ASSET_COLS = [
  { key: "has_description" as const, label: "Desc" },
  { key: "has_videos"      as const, label: "Videos" },
  { key: "has_thumbnail"   as const, label: "Thumb" },
  { key: "has_photos"      as const, label: "Photos" },
  { key: "has_storyboard"  as const, label: "Story" },
]

function missingLabels(scene: Scene): string[] {
  return ASSET_COLS.filter(a => !scene[a.key]).map(a => a.label)
}

const UNDO_DURATION_MS = 7000

interface UndoEntry {
  id: string
  decision: "Approved" | "Rejected"
  previousStatus: string
  approval: Approval
}

interface Props {
  initialApprovals: Approval[]
  missingScenes: Scene[]
  missingTotal: number
  scripts: Script[]
  idToken: string | undefined
}

export function TriageFeed({
  initialApprovals,
  missingScenes,
  missingTotal,
  scripts,
  idToken: serverIdToken,
}: Props) {
  const idToken = useIdToken(serverIdToken)

  const [approvals, setApprovals] = useState(initialApprovals)
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set())
  const [undoEntry, setUndoEntry] = useState<UndoEntry | null>(null)
  const [undoProgress, setUndoProgress] = useState(100)
  const undoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const undoFinalizeRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const clearUndoTimers = useCallback(() => {
    if (undoTimerRef.current) { clearInterval(undoTimerRef.current); undoTimerRef.current = null }
    if (undoFinalizeRef.current) { clearTimeout(undoFinalizeRef.current); undoFinalizeRef.current = null }
  }, [])

  const commitDecision = useCallback(async (approval: Approval, decision: "Approved" | "Rejected", notes: string) => {
    if (!idToken) return
    try {
      await api(idToken).approvals.decide(approval.approval_id, { decision, notes })
    } catch {
      // Rollback on failure
      setApprovals(prev => [...prev, approval].sort((a, b) => a.submitted_at.localeCompare(b.submitted_at)))
    }
  }, [idToken])

  const handleDecision = useCallback((approval: Approval, decision: "Approved" | "Rejected", notes = "") => {
    clearUndoTimers()

    setApprovals(prev => prev.filter(a => a.approval_id !== approval.approval_id))
    setPendingIds(prev => {
      const next = new Set(prev)
      next.add(approval.approval_id)
      return next
    })
    setUndoEntry({ id: approval.approval_id, decision, previousStatus: approval.status, approval })
    setUndoProgress(100)

    const start = Date.now()
    undoTimerRef.current = setInterval(() => {
      const pct = Math.max(0, 100 - ((Date.now() - start) / UNDO_DURATION_MS) * 100)
      setUndoProgress(pct)
    }, 60)

    undoFinalizeRef.current = setTimeout(() => {
      clearUndoTimers()
      setUndoEntry(null)
      setPendingIds(prev => {
        const next = new Set(prev)
        next.delete(approval.approval_id)
        return next
      })
      void commitDecision(approval, decision, notes)
    }, UNDO_DURATION_MS)

    // Close reject form if it was open
    setRejectingId(null)
    setRejectReason("")
  }, [clearUndoTimers, commitDecision])

  const handleUndo = useCallback(() => {
    if (!undoEntry) return
    clearUndoTimers()
    setApprovals(prev => [...prev, undoEntry.approval].sort((a, b) => a.submitted_at.localeCompare(b.submitted_at)))
    setPendingIds(prev => {
      const next = new Set(prev)
      next.delete(undoEntry.id)
      return next
    })
    setUndoEntry(null)
  }, [undoEntry, clearUndoTimers])

  const handleDismissUndo = useCallback(() => {
    if (!undoEntry) return
    const { approval, decision } = undoEntry
    clearUndoTimers()
    setUndoEntry(null)
    setPendingIds(prev => {
      const next = new Set(prev)
      next.delete(approval.approval_id)
      return next
    })
    void commitDecision(approval, decision, "")
  }, [undoEntry, clearUndoTimers, commitDecision])

  function openReject(id: string) {
    setRejectingId(id)
    setRejectReason("")
    setTimeout(() => textareaRef.current?.focus(), 60)
  }

  const hasAnything = approvals.length > 0 || missingScenes.length > 0 || scripts.length > 0

  return (
    <>
      <Section title="Waiting on You" subtitle={hasAnything ? undefined : "Nothing blocking — inbox clear."}>
        {/* Approvals */}
        <SubSection label="Approvals" count={approvals.length} href="/approvals" emptyLabel="No approvals pending ✓" empty={approvals.length === 0}>
          {approvals.slice(0, 5).map(appr => {
            const isRejecting = rejectingId === appr.approval_id
            const color = STUDIO_COLOR[appr.studio] ?? "var(--color-text-muted)"
            const abbr = STUDIO_ABBR[appr.studio] ?? appr.studio
            const typeLabel = CONTENT_TYPE_LABEL[appr.content_type] ?? appr.content_type
            return (
              <div
                key={appr.approval_id}
                style={{
                  padding: "8px 14px",
                  borderBottom: "1px solid var(--color-border-subtle)",
                  display: "flex",
                  flexDirection: "column",
                  gap: isRejecting ? 8 : 0,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  {/* Studio badge */}
                  <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                    padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                    background: `color-mix(in srgb, ${color} 14%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${color} 26%, transparent)`,
                    color,
                  }}>{abbr}</span>

                  <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--color-text)", flexShrink: 0 }}>
                    {appr.scene_id}
                  </span>

                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                    {typeLabel}
                  </span>

                  {!isRejecting && (
                    <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                      <button
                        onClick={() => handleDecision(appr, "Approved")}
                        disabled={!idToken}
                        style={{
                          padding: "3px 10px", borderRadius: 3, fontSize: 11, fontWeight: 500,
                          cursor: idToken ? "pointer" : "not-allowed",
                          background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                          color: "var(--color-lime)",
                          border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                        }}
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => openReject(appr.approval_id)}
                        style={{
                          padding: "3px 10px", borderRadius: 3, fontSize: 11,
                          cursor: "pointer",
                          background: "transparent",
                          color: "var(--color-text-muted)",
                          border: "1px solid var(--color-border)",
                        }}
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>

                {isRejecting && (
                  <>
                    <textarea
                      ref={textareaRef}
                      value={rejectReason}
                      onChange={e => setRejectReason(e.target.value)}
                      placeholder="What needs to change?"
                      maxLength={280}
                      rows={2}
                      style={{
                        width: "100%", resize: "none",
                        background: "var(--color-elevated)",
                        border: "1px solid var(--color-border)",
                        borderRadius: 3,
                        color: "var(--color-text)",
                        fontSize: 12, lineHeight: 1.5,
                        padding: "6px 9px",
                        fontFamily: "var(--font-sans)",
                        outline: "none",
                      }}
                    />
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 10, color: rejectReason.length < 10 ? "var(--color-text-faint)" : "var(--color-ok)" }}>
                        {rejectReason.length < 10 ? "Minimum 10 characters" : "✓"}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--color-text-faint)", marginLeft: "auto" }}>{rejectReason.length}/280</span>
                      <button
                        onClick={() => { setRejectingId(null); setRejectReason("") }}
                        style={{
                          padding: "3px 10px", borderRadius: 3, fontSize: 11,
                          cursor: "pointer",
                          background: "transparent",
                          color: "var(--color-text-muted)",
                          border: "1px solid var(--color-border)",
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleDecision(appr, "Rejected", rejectReason)}
                        disabled={rejectReason.length < 10}
                        style={{
                          padding: "3px 10px", borderRadius: 3, fontSize: 11, fontWeight: 500,
                          cursor: rejectReason.length < 10 ? "not-allowed" : "pointer",
                          opacity: rejectReason.length < 10 ? 0.45 : 1,
                          background: "color-mix(in srgb, var(--color-err) 12%, transparent)",
                          color: "var(--color-err)",
                          border: "1px solid color-mix(in srgb, var(--color-err) 28%, transparent)",
                        }}
                      >
                        Confirm
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })}
          {approvals.length > 5 && (
            <SeeAll href="/approvals" label={`See all ${approvals.length} →`} />
          )}
        </SubSection>

        {/* Missing Assets */}
        <SubSection
          label="Missing Assets"
          count={missingTotal}
          href="/missing"
          emptyLabel="All assets accounted for ✓"
          empty={missingScenes.length === 0}
        >
          {missingScenes.slice(0, 5).map(scene => {
            const color = STUDIO_COLOR[scene.studio] ?? "var(--color-text-muted)"
            const abbr = STUDIO_ABBR[scene.studio] ?? scene.studio
            const missing = missingLabels(scene)
            const dateStr = (scene.release_date ?? "").slice(0, 10)
            return (
              <Link
                key={scene.id}
                href={`/missing?scene=${encodeURIComponent(scene.id)}`}
                style={{
                  padding: "8px 14px",
                  borderBottom: "1px solid var(--color-border-subtle)",
                  display: "flex", alignItems: "center", gap: 10,
                  textDecoration: "none", color: "inherit",
                }}
                className="hover:bg-[--color-elevated]"
              >
                <span style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                  padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                  background: `color-mix(in srgb, ${color} 14%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${color} 26%, transparent)`,
                  color,
                }}>{abbr}</span>

                <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--color-text)", flexShrink: 0 }}>
                  {scene.id}
                </span>

                <span style={{ display: "flex", flexWrap: "wrap", gap: 3, flex: 1, minWidth: 0 }}>
                  {missing.map(m => (
                    <span key={m} style={{
                      fontSize: 10, fontWeight: 600, padding: "0 5px", borderRadius: 3,
                      background: "color-mix(in srgb, var(--color-err) 12%, transparent)",
                      color: "var(--color-err)",
                    }}>{m}</span>
                  ))}
                </span>

                {dateStr && (
                  <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                    {dateStr}
                  </span>
                )}
              </Link>
            )
          })}
          {missingTotal > missingScenes.length && (
            <SeeAll href="/missing" label={`See all ${missingTotal} →`} />
          )}
        </SubSection>

        {/* Scripts Queued — only rendered when non-empty */}
        {scripts.length > 0 && (
          <SubSection label="Scripts Queued" count={scripts.length} href="/scripts" empty={false}>
            {scripts.slice(0, 5).map(script => {
              const color = STUDIO_COLOR[script.studio] ?? "var(--color-text-muted)"
              const abbr = STUDIO_ABBR[script.studio] ?? script.studio
              const talent = [script.female, script.male].filter(Boolean).join(" / ")
              return (
                <div
                  key={script.id}
                  style={{
                    padding: "8px 14px",
                    borderBottom: "1px solid var(--color-border-subtle)",
                    display: "flex", alignItems: "center", gap: 10,
                  }}
                >
                  <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                    padding: "1px 5px", borderRadius: 3, flexShrink: 0,
                    background: `color-mix(in srgb, ${color} 14%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${color} 26%, transparent)`,
                    color,
                  }}>{abbr}</span>

                  <span style={{ fontSize: 12, color: "var(--color-text)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                    {talent || "—"}
                  </span>

                  {script.shoot_date && (
                    <span style={{ fontSize: 10, color: "var(--color-text-faint)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
                      {script.shoot_date}
                    </span>
                  )}

                  <Link
                    href="/scripts"
                    style={{
                      padding: "3px 10px", borderRadius: 3, fontSize: 11, fontWeight: 500,
                      textDecoration: "none",
                      background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                      color: "var(--color-lime)",
                      border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                      flexShrink: 0,
                    }}
                  >
                    Start
                  </Link>
                </div>
              )
            })}
            {scripts.length > 5 && <SeeAll href="/scripts" label={`See all ${scripts.length} →`} />}
          </SubSection>
        )}
      </Section>

      {undoEntry && (
        <UndoToast
          decision={undoEntry.decision}
          progress={undoProgress}
          onUndo={handleUndo}
          onDismiss={handleDismissUndo}
        />
      )}
    </>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "9px 14px", borderBottom: "1px solid var(--color-border)" }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {subtitle && (
          <p style={{ margin: "3px 0 0", fontSize: 11, color: "var(--color-text-faint)" }}>{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  )
}

function SubSection({
  label,
  count,
  href,
  emptyLabel,
  empty,
  children,
}: {
  label: string
  count: number
  href: string
  emptyLabel?: string
  empty: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <div style={{
        padding: "7px 14px",
        display: "flex", alignItems: "baseline", gap: 8,
        borderBottom: empty ? "none" : "1px solid var(--color-border-subtle)",
        background: "var(--color-base)",
      }}>
        <Link
          href={href}
          style={{
            fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
            color: "var(--color-text-muted)", textDecoration: "none",
          }}
          className="hover:text-[--color-text]"
        >
          {label}
        </Link>
        <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
          · {count}
        </span>
      </div>
      {empty ? (
        <div style={{ padding: "10px 14px", fontSize: 11, color: "var(--color-text-faint)" }}>
          {emptyLabel}
        </div>
      ) : (
        children
      )}
    </div>
  )
}

function SeeAll({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      style={{
        display: "block",
        padding: "7px 14px",
        fontSize: 11,
        color: "var(--color-text-muted)",
        textDecoration: "none",
        textAlign: "center",
      }}
      className="hover:bg-[--color-elevated]"
    >
      {label}
    </Link>
  )
}

function UndoToast({
  decision,
  progress,
  onUndo,
  onDismiss,
}: {
  decision: "Approved" | "Rejected"
  progress: number
  onUndo: () => void
  onDismiss: () => void
}) {
  const barColor = decision === "Approved" ? "var(--color-ok)" : "var(--color-err)"
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 500,
        background: "var(--color-elevated)",
        border: "1px solid var(--color-border)",
        borderRadius: 4,
        overflow: "hidden",
        minWidth: 200,
        boxShadow: "0 8px 24px rgba(0,0,0,.4)",
        animation: "toastSlideUp 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
      }}
    >
      <div
        aria-hidden="true"
        style={{
          height: 2,
          background: barColor,
          width: "100%",
          transform: `scaleX(${progress / 100})`,
          transformOrigin: "left",
          transition: "transform 60ms linear",
        }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 12px" }}>
        <span style={{ fontSize: 12, color: "var(--color-text)", flex: 1 }}>{decision}</span>
        <button
          onClick={onUndo}
          style={{
            fontSize: 12, fontWeight: 600, color: "var(--color-lime)",
            background: "none", border: "none", padding: "0 2px", cursor: "pointer",
            letterSpacing: "0.01em",
          }}
        >
          Undo
        </button>
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            display: "flex", alignItems: "center",
            color: "var(--color-text-muted)",
            background: "none", border: "none", padding: "0 2px", cursor: "pointer",
          }}
        >
          <X size={12} />
        </button>
      </div>
    </div>
  )
}
