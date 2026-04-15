"use client"

import { useState, useCallback, useEffect, useRef, useMemo } from "react"
import { X, ChevronRight } from "lucide-react"
import { FilterTabs } from "@/components/ui/filter-tabs"
import { StudioBadge } from "@/components/ui/studio-badge"
import { api, type Approval } from "@/lib/api"
import { STUDIO_COLOR } from "@/lib/studio-colors"

// ─── Constants ───────────────────────────────────────────────────────────────

const STATUSES = ["All", "Pending", "Approved", "Rejected"]

const STATUS_COLOR: Record<string, string> = {
  Pending:  "var(--color-warn)",
  Approved: "var(--color-ok)",
  Rejected: "var(--color-err)",
}

const CONTENT_TYPE_LABEL: Record<string, string> = {
  description:  "Description",
  script:       "Script",
  compilation:  "Compilation",
}

const UNDO_DURATION_MS = 7000

// ─── Helpers ─────────────────────────────────────────────────────────────────

type ParsedContent =
  | { kind: "sections"; sections: { label: string; value: string }[] }
  | { kind: "raw"; text: string }
  | { kind: "empty" }

function parseContentJson(raw: string | null | undefined): ParsedContent {
  if (!raw?.trim()) return { kind: "empty" }
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed === "string") {
      return parsed.trim() ? { kind: "raw", text: parsed } : { kind: "empty" }
    }
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      const sections = Object.entries(parsed)
        .filter(([, v]) => typeof v === "string" && (v as string).trim())
        .map(([k, v]) => ({
          label: k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
          value: v as string,
        }))
      return sections.length ? { kind: "sections", sections } : { kind: "empty" }
    }
  } catch {
    // not JSON — treat as raw text
  }
  return raw.trim() ? { kind: "raw", text: raw } : { kind: "empty" }
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface UndoEntry {
  approvalId: string
  previousStatus: string
  decision: "Approved" | "Rejected"
}

// ─── Undo Toast ───────────────────────────────────────────────────────────────

interface UndoToastProps {
  decision: "Approved" | "Rejected"
  progress: number // 0–100
  onUndo: () => void
  onDismiss: () => void
}

function UndoToast({ decision, progress, onUndo, onDismiss }: UndoToastProps) {
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
        boxShadow: "0 8px 32px color-mix(in srgb, #000 55%, transparent)",
        animation: "toastSlideUp 200ms cubic-bezier(0.16, 1, 0.3, 1) both",
      }}
    >
      {/* Countdown bar */}
      <div
        aria-hidden="true"
        style={{
          height: 2,
          background: barColor,
          width: `${progress}%`,
          transition: "width 60ms linear",
        }}
      />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "9px 12px",
        }}
      >
        <span style={{ fontSize: 12, color: "var(--color-text)", flex: 1 }}>
          {decision}
        </span>
        <button
          onClick={onUndo}
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-lime)",
            background: "none",
            border: "none",
            padding: "0 2px",
            cursor: "pointer",
            letterSpacing: "0.01em",
          }}
        >
          Undo
        </button>
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            display: "flex",
            alignItems: "center",
            color: "var(--color-text-muted)",
            background: "none",
            border: "none",
            padding: "0 2px",
            cursor: "pointer",
          }}
        >
          <X size={12} />
        </button>
      </div>
    </div>
  )
}

// ─── Approval Panel ───────────────────────────────────────────────────────────

interface PanelProps {
  approval: Approval
  onClose: () => void
  onApprove: () => void
  onReject: (reason: string) => void
}

function ApprovalPanel({ approval, onClose, onApprove, onReject }: PanelProps) {
  const [rejectExpanded, setRejectExpanded] = useState(false)
  const [reason, setReason] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const studioColor = STUDIO_COLOR[approval.studio] ?? "var(--color-text-muted)"
  const contentLabel = CONTENT_TYPE_LABEL[approval.content_type] ?? approval.content_type
  const isPending = approval.status === "Pending"
  const parsed = parseContentJson(approval.content_json)

  // Focus textarea after reject form expands
  useEffect(() => {
    if (rejectExpanded) {
      const t = setTimeout(() => textareaRef.current?.focus(), 120)
      return () => clearTimeout(t)
    }
  }, [rejectExpanded])

  function handleRejectConfirm() {
    onReject(reason)
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        maxHeight: "min(680px, calc(100vh - var(--spacing-topbar) - 120px))",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 4,
        overflow: "hidden",
        animation: "panelSlideIn 260ms cubic-bezier(0.16, 1, 0.3, 1) both",
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: "12px 14px",
          borderBottom: "1px solid var(--color-border)",
          background: `color-mix(in srgb, ${studioColor} 7%, var(--color-surface))`,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <StudioBadge studio={approval.studio} />
              {contentLabel && (
                <span style={{
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.07em",
                  textTransform: "uppercase" as const,
                  color: studioColor,
                }}>
                  {contentLabel}
                </span>
              )}
            </div>
            <div
              className="font-mono"
              style={{ fontSize: 13, color: "var(--color-text)", marginBottom: 3 }}
            >
              {approval.scene_id || "—"}
            </div>
            <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              {approval.submitted_by}
              {approval.submitted_at && (
                <span style={{ marginLeft: 8, color: "var(--color-text-faint)", fontSize: 10 }}>
                  {approval.submitted_at.slice(0, 10)}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="transition-colors"
            style={{
              color: "var(--color-text-muted)",
              background: "none",
              border: "none",
              padding: 4,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              borderRadius: 3,
              marginTop: -2,
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* ── Content body ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 14px" }}>
        {parsed.kind === "sections" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {parsed.sections.map(({ label, value }) => (
              <div key={label}>
                <div style={{
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.07em",
                  textTransform: "uppercase" as const,
                  color: studioColor,
                  opacity: 0.75,
                  marginBottom: 6,
                }}>
                  {label}
                </div>
                <p style={{
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: "var(--color-text)",
                  margin: 0,
                  whiteSpace: "pre-wrap",
                }}>
                  {value}
                </p>
              </div>
            ))}
          </div>
        )}

        {parsed.kind === "raw" && (
          <pre style={{
            fontSize: 12,
            lineHeight: 1.7,
            color: "var(--color-text)",
            whiteSpace: "pre-wrap",
            fontFamily: "var(--font-sans)",
            margin: 0,
          }}>
            {parsed.text}
          </pre>
        )}

        {parsed.kind === "empty" && (
          <p style={{ fontSize: 12, color: "var(--color-text-faint)", fontStyle: "italic", margin: 0 }}>
            No content to preview.
          </p>
        )}
      </div>

      {/* ── Footer ── */}
      <div
        style={{
          borderTop: "1px solid var(--color-border)",
          padding: "10px 14px",
          flexShrink: 0,
          background: "var(--color-base)",
        }}
      >
        {isPending ? (
          <>
            {/* Rejection reason — grid-template-rows expand trick */}
            <div style={{
              display: "grid",
              gridTemplateRows: rejectExpanded ? "1fr" : "0fr",
              transition: "grid-template-rows 200ms cubic-bezier(0.16, 1, 0.3, 1)",
            }}>
              <div style={{ overflow: "hidden" }}>
                <div style={{ paddingTop: 2, paddingBottom: 10 }}>
                  <label
                    htmlFor="reject-reason"
                    style={{ display: "block", fontSize: 11, color: "var(--color-text-muted)", marginBottom: 5 }}
                  >
                    Reason for rejection
                  </label>
                  <textarea
                    ref={textareaRef}
                    id="reject-reason"
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                    placeholder="What needs to change?"
                    maxLength={280}
                    rows={3}
                    style={{
                      width: "100%",
                      resize: "none",
                      background: "var(--color-elevated)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 3,
                      color: "var(--color-text)",
                      fontSize: 12,
                      lineHeight: 1.55,
                      padding: "7px 10px",
                      fontFamily: "var(--font-sans)",
                      outline: "none",
                    }}
                  />
                  <div style={{
                    fontSize: 10,
                    color: "var(--color-text-faint)",
                    textAlign: "right",
                    marginTop: 3,
                  }}>
                    {reason.length}/280
                  </div>
                </div>
              </div>
            </div>

            {/* Buttons */}
            {!rejectExpanded ? (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={onApprove}
                  className="transition-colors"
                  style={{
                    flex: 1,
                    padding: "8px 0",
                    borderRadius: 3,
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: "pointer",
                    background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                    color: "var(--color-lime)",
                    border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                  }}
                >
                  Approve
                </button>
                <button
                  onClick={() => setRejectExpanded(true)}
                  className="transition-colors"
                  style={{
                    flex: 1,
                    padding: "8px 0",
                    borderRadius: 3,
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: "pointer",
                    background: "transparent",
                    color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  Reject
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => { setRejectExpanded(false); setReason("") }}
                  className="transition-colors"
                  style={{
                    padding: "8px 12px",
                    borderRadius: 3,
                    fontSize: 13,
                    cursor: "pointer",
                    background: "transparent",
                    color: "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleRejectConfirm}
                  disabled={reason.length < 10}
                  className="transition-colors"
                  style={{
                    flex: 1,
                    padding: "8px 0",
                    borderRadius: 3,
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: reason.length < 10 ? "not-allowed" : "pointer",
                    opacity: reason.length < 10 ? 0.45 : 1,
                    background: "color-mix(in srgb, var(--color-err) 12%, transparent)",
                    color: "var(--color-err)",
                    border: "1px solid color-mix(in srgb, var(--color-err) 28%, transparent)",
                  }}
                >
                  Confirm Rejection
                </button>
              </div>
            )}
          </>
        ) : (
          /* Read-only footer for resolved approvals */
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              className="inline-flex items-center px-1.5 py-0.5 rounded-sm"
              style={{
                fontSize: 10,
                fontWeight: 500,
                background: `color-mix(in srgb, ${STATUS_COLOR[approval.status] ?? "var(--color-text-muted)"} 15%, transparent)`,
                color: STATUS_COLOR[approval.status] ?? "var(--color-text-muted)",
                border: `1px solid color-mix(in srgb, ${STATUS_COLOR[approval.status] ?? "var(--color-text-muted)"} 25%, transparent)`,
              }}
            >
              {approval.status}
            </span>
            {approval.decided_by && (
              <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                by {approval.decided_by}
              </span>
            )}
            {approval.notes && (
              <span style={{ fontSize: 11, color: "var(--color-text-muted)", flex: 1, fontStyle: "italic" }}>
                · {approval.notes}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  initialApprovals: Approval[]
  error: string | null
  idToken: string | undefined
}

export function ApprovalList({ initialApprovals, error: initialError, idToken }: Props) {
  const [approvals, setApprovals] = useState<Approval[]>(initialApprovals)
  const [error, setError] = useState<string | null>(initialError)
  const [statusFilter, setStatusFilter] = useState("Pending")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [undo, setUndo] = useState<UndoEntry | null>(null)
  const [undoProgress, setUndoProgress] = useState(100)

  // Refs for timers — don't trigger re-renders
  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Tracks pending API commit even after the undo toast is dismissed
  const pendingCommitRef = useRef<{
    approvalId: string
    decision: "Approved" | "Rejected"
    notes?: string
  } | null>(null)

  const client = useMemo(() => api(idToken ?? null), [idToken])

  const selectedApproval = approvals.find(a => a.approval_id === selectedId) ?? null

  const filtered = useMemo(() =>
    statusFilter === "All"
      ? approvals
      : approvals.filter(a => a.status === statusFilter),
    [approvals, statusFilter]
  )

  const statusCounts = useMemo(() => ({
    All:      approvals.length,
    Pending:  approvals.filter(a => a.status === "Pending").length,
    Approved: approvals.filter(a => a.status === "Approved").length,
    Rejected: approvals.filter(a => a.status === "Rejected").length,
  }), [approvals])

  // Escape key closes panel
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && selectedId) setSelectedId(null)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [selectedId])

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current)
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
    }
  }, [])

  function startProgressCountdown() {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
    setUndoProgress(100)
    const startTime = Date.now()
    progressIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime
      const pct = Math.max(0, 100 - (elapsed / UNDO_DURATION_MS) * 100)
      setUndoProgress(pct)
      if (pct === 0 && progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current)
        progressIntervalRef.current = null
      }
    }, 60)
  }

  const commitDecision = useCallback(async (
    approvalId: string,
    decision: "Approved" | "Rejected",
    notes?: string
  ) => {
    try {
      const updated = await client.approvals.decide(approvalId, { decision, notes })
      setApprovals(prev => prev.map(a => a.approval_id === updated.approval_id ? updated : a))
    } catch (e) {
      setApprovals(prev =>
        prev.map(a => a.approval_id === approvalId ? { ...a, status: "Pending" } : a)
      )
      setError(e instanceof Error ? e.message : "Couldn't save. Try again.")
    }
  }, [client])

  const decide = useCallback((decision: "Approved" | "Rejected", notes?: string) => {
    if (!selectedApproval) return
    const { approval_id, status: previousStatus } = selectedApproval

    // If there's an in-flight commit from a previous decision, fire it immediately
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
      if (pendingCommitRef.current) {
        const { approvalId, decision: prevDecision, notes: prevNotes } = pendingCommitRef.current
        commitDecision(approvalId, prevDecision, prevNotes)
        pendingCommitRef.current = null
      }
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
      progressIntervalRef.current = null
    }

    // Optimistic update
    setApprovals(prev =>
      prev.map(a => a.approval_id === approval_id ? { ...a, status: decision } : a)
    )

    // Close panel
    setSelectedId(null)

    // Store pending commit in ref (survives toast dismissal)
    pendingCommitRef.current = { approvalId: approval_id, decision, notes }

    // Start undo window
    startProgressCountdown()
    setUndo({ approvalId: approval_id, previousStatus, decision })

    undoTimerRef.current = setTimeout(() => {
      if (pendingCommitRef.current) {
        commitDecision(pendingCommitRef.current.approvalId, pendingCommitRef.current.decision, pendingCommitRef.current.notes)
        pendingCommitRef.current = null
      }
      setUndo(null)
      undoTimerRef.current = null
    }, UNDO_DURATION_MS)
  }, [selectedApproval, commitDecision])

  const handleUndo = useCallback(() => {
    if (!undo) return

    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
      progressIntervalRef.current = null
    }

    // Cancel pending commit
    pendingCommitRef.current = null

    // Revert optimistic update
    setApprovals(prev =>
      prev.map(a => a.approval_id === undo.approvalId ? { ...a, status: undo.previousStatus } : a)
    )

    // Reopen the panel for the reverted item
    setSelectedId(undo.approvalId)
    setUndo(null)
    setUndoProgress(100)
  }, [undo])

  const handleDismissUndo = useCallback(() => {
    // Just hide the toast; the timer still runs and commits
    setUndo(null)
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
      progressIntervalRef.current = null
    }
  }, [])

  function selectRow(approvalId: string) {
    setSelectedId(prev => prev === approvalId ? null : approvalId)
  }

  return (
    <div style={{ position: "relative" }}>
      {/* Filter bar */}
      <div className="mb-4">
        <FilterTabs
          options={STATUSES}
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setSelectedId(null) }}
          counts={statusCounts}
        />
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="rounded mb-4"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "10px 12px",
            fontSize: 12,
            background: "color-mix(in srgb, var(--color-err) 10%, var(--color-surface))",
            border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
            color: "var(--color-err)",
          }}
        >
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            aria-label="Dismiss error"
            style={{ color: "inherit", opacity: 0.7, background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex" }}
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* Master-detail layout */}
      <div style={{ display: "flex", alignItems: "flex-start" }}>
        {/* List zone */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {filtered.length === 0 && !error && (
            <p style={{ fontSize: 13, color: "var(--color-text-muted)", paddingTop: 8 }}>
              {statusFilter === "Pending"
                ? "No pending approvals."
                : statusFilter === "All"
                  ? "Nothing to review."
                  : `No ${statusFilter.toLowerCase()} approvals.`}
            </p>
          )}

          {filtered.length > 0 && (
            <div
              className="rounded overflow-hidden"
              style={{ border: "1px solid var(--color-border)" }}
            >
              <table className="w-full" style={{ borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-border)" }}>
                    {["Scene", "Studio", "Type", "Submitted by", "Date", "Status", ""].map((h, i) => (
                      <th
                        key={i}
                        className="text-left px-3 py-2 font-medium"
                        style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((approval, i) => {
                    const isSelected = approval.approval_id === selectedId
                    const rowColor = STUDIO_COLOR[approval.studio] ?? "var(--color-text-muted)"
                    return (
                      <tr
                        key={approval.approval_id}
                        onClick={() => selectRow(approval.approval_id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault()
                            selectRow(approval.approval_id)
                          }
                        }}
                        role="row"
                        aria-selected={isSelected}
                        tabIndex={0}
                        aria-label={`Review ${CONTENT_TYPE_LABEL[approval.content_type] ?? approval.content_type} for scene ${approval.scene_id}`}
                        style={{
                          borderBottom: i < filtered.length - 1
                            ? "1px solid var(--color-border-subtle)"
                            : undefined,
                          background: isSelected
                            ? `color-mix(in srgb, ${rowColor} 8%, var(--color-elevated))`
                            : undefined,
                          cursor: "pointer",
                          outline: "none",
                          transition: "background 120ms",
                        }}
                        className={!isSelected ? "hover:bg-[--color-elevated]" : ""}
                      >
                        <td className="px-3 py-2.5 font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                          {approval.scene_id || "—"}
                        </td>
                        <td className="px-3 py-2.5 whitespace-nowrap">
                          {approval.studio
                            ? <StudioBadge studio={approval.studio} />
                            : <span style={{ color: "var(--color-text-faint)" }}>—</span>}
                        </td>
                        <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                          {CONTENT_TYPE_LABEL[approval.content_type] ?? approval.content_type ?? "—"}
                        </td>
                        <td className="px-3 py-2.5" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                          {approval.submitted_by || "—"}
                        </td>
                        <td className="px-3 py-2.5 font-mono" style={{ fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                          {approval.submitted_at ? approval.submitted_at.slice(0, 10) : "—"}
                        </td>
                        <td className="px-3 py-2.5 whitespace-nowrap">
                          <span
                            className="inline-flex items-center px-1.5 py-0.5 rounded-sm"
                            style={{
                              fontSize: 10,
                              fontWeight: 500,
                              background: `color-mix(in srgb, ${STATUS_COLOR[approval.status] ?? "var(--color-text-muted)"} 15%, transparent)`,
                              color: STATUS_COLOR[approval.status] ?? "var(--color-text-muted)",
                              border: `1px solid color-mix(in srgb, ${STATUS_COLOR[approval.status] ?? "var(--color-text-muted)"} 25%, transparent)`,
                            }}
                          >
                            {approval.status}
                          </span>
                        </td>
                        <td className="px-2 py-2.5" style={{ width: 28, textAlign: "right" }}>
                          <ChevronRight
                            size={12}
                            aria-hidden="true"
                            style={{
                              color: isSelected ? rowColor : "var(--color-border)",
                              transition: "color 150ms",
                            }}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Panel wrapper — animates width open/closed */}
        <div
          style={{
            width: selectedApproval ? 420 : 0,
            flexShrink: 0,
            overflow: "hidden",
            marginLeft: selectedApproval ? 12 : 0,
            transition: "width 260ms cubic-bezier(0.16, 1, 0.3, 1), margin-left 260ms cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        >
          {selectedApproval && (
            <div style={{ width: 420 }}>
              <ApprovalPanel
                key={selectedApproval.approval_id}
                approval={selectedApproval}
                onClose={() => setSelectedId(null)}
                onApprove={() => decide("Approved")}
                onReject={(reason) => decide("Rejected", reason)}
              />
            </div>
          )}
        </div>
      </div>

      {/* Undo toast */}
      {undo && (
        <UndoToast
          decision={undo.decision}
          progress={undoProgress}
          onUndo={handleUndo}
          onDismiss={handleDismissUndo}
        />
      )}
    </div>
  )
}
