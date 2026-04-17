"use client"

import { useState, useCallback, useEffect, useRef, useMemo } from "react"
import { X, ChevronRight } from "lucide-react"
import { FilterTabs } from "@/components/ui/filter-tabs"
import { StudioBadge } from "@/components/ui/studio-badge"
import { api, ApiError, type Approval } from "@/lib/api"
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
  approvalIds: string[]
  previousStatuses: Record<string, string>
  decision: "Approved" | "Rejected"
}

// ─── Undo Toast ───────────────────────────────────────────────────────────────

interface UndoToastProps {
  decision: "Approved" | "Rejected"
  count: number
  progress: number // 0–100
  onUndo: () => void
  onDismiss: () => void
}

function UndoToast({ decision, count, progress, onUndo, onDismiss }: UndoToastProps) {
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
      {/* Countdown bar — scaleX avoids layout reflow on every tick */}
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
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "8px 12px",
        }}
      >
        <span style={{ fontSize: 12, color: "var(--color-text)", flex: 1 }}>
          {count > 1 ? `${decision} (${count})` : decision}
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
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 3 }}>
                    <span style={{ fontSize: 10, color: reason.length < 10 ? "var(--color-text-faint)" : "var(--color-ok)" }}>
                      {reason.length < 10 ? "Minimum 10 characters" : "✓"}
                    </span>
                    <span style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                      {reason.length}/280
                    </span>
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
                  {reason.length < 10 ? "Add more detail to confirm" : "Confirm Rejection"}
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
  const [retryFn, setRetryFn] = useState<(() => void) | null>(null)
  const [statusFilter, setStatusFilter] = useState("Pending")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [bulkSelected, setBulkSelected] = useState<Set<string>>(new Set())
  const [undo, setUndo] = useState<UndoEntry | null>(null)
  const [undoProgress, setUndoProgress] = useState(100)

  // Refs for timers — don't trigger re-renders
  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Tracks pending API commit even after the undo toast is dismissed (supports single and bulk)
  const pendingCommitRef = useRef<{
    approvalIds: string[]
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

  // Pending items visible in current filter — used for select-all checkbox
  const pendingInView = useMemo(() =>
    filtered.filter(a => a.status === "Pending"),
    [filtered]
  )

  const allPendingSelected = pendingInView.length > 0 &&
    pendingInView.every(a => bulkSelected.has(a.approval_id))

  const somePendingSelected = !allPendingSelected &&
    pendingInView.some(a => bulkSelected.has(a.approval_id))

  function toggleSelectAll() {
    if (allPendingSelected) {
      setBulkSelected(new Set())
    } else {
      setBulkSelected(new Set(pendingInView.map(a => a.approval_id)))
    }
  }

  function toggleBulkSelect(approvalId: string) {
    setBulkSelected(prev => {
      const next = new Set(prev)
      if (next.has(approvalId)) { next.delete(approvalId) } else { next.add(approvalId) }
      return next
    })
  }

  // Escape: close panel first, then clear selection
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      if (selectedId) setSelectedId(null)
      else if (bulkSelected.size > 0) setBulkSelected(new Set())
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [selectedId, bulkSelected])

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
      setRetryFn(null)
    } catch (e) {
      // Roll back optimistic update
      setApprovals(prev =>
        prev.map(a => a.approval_id === approvalId ? { ...a, status: "Pending" } : a)
      )
      if (e instanceof ApiError && e.status === 401) {
        setError("Session expired — refresh the page to sign in again.")
        setRetryFn(null)
      } else if (e instanceof ApiError) {
        setError(`Couldn't save: ${e.message}`)
        setRetryFn(() => () => commitDecision(approvalId, decision, notes))
      } else {
        setError("Network error — check your connection and try again.")
        setRetryFn(() => () => commitDecision(approvalId, decision, notes))
      }
    }
  }, [client])

  // Flush any pending in-flight commit immediately — shared by decide() and decideBulk()
  function flushPending() {
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
      progressIntervalRef.current = null
    }
    if (pendingCommitRef.current) {
      const { approvalIds, decision: d, notes } = pendingCommitRef.current
      // allSettled so one failed id doesn't cancel the rest; commitDecision
      // already handles its own rollback/retry per id.
      Promise.allSettled(approvalIds.map(id => commitDecision(id, d, notes)))
      pendingCommitRef.current = null
    }
  }

  // Decide on a specific approval (panel OR inline row). Shared so the panel's
  // undo+commit lifecycle is identical whether you went through the detail view
  // or approved straight from the row.
  const decideApproval = useCallback((
    approval: Approval,
    decision: "Approved" | "Rejected",
    notes?: string,
  ) => {
    const { approval_id, status: previousStatus } = approval

    // Guard: an approval is immutable once decided server-side.
    // Stale list state would let a user flip Approved → Rejected.
    if (previousStatus !== "Pending") {
      setError(`${approval_id} is already ${previousStatus.toLowerCase()}.`)
      return
    }

    flushPending()

    setApprovals(prev =>
      prev.map(a => a.approval_id === approval_id ? { ...a, status: decision } : a)
    )
    if (selectedId === approval_id) setSelectedId(null)

    pendingCommitRef.current = { approvalIds: [approval_id], decision, notes }
    startProgressCountdown()
    setUndo({ approvalIds: [approval_id], previousStatuses: { [approval_id]: previousStatus }, decision })

    undoTimerRef.current = setTimeout(() => {
      if (pendingCommitRef.current) {
        const { approvalIds, decision: d, notes: n } = pendingCommitRef.current
        Promise.allSettled(approvalIds.map(id => commitDecision(id, d, n)))
        pendingCommitRef.current = null
      }
      setUndo(null)
      undoTimerRef.current = null
    }, UNDO_DURATION_MS)
  }, [selectedId, commitDecision])

  const decide = useCallback((decision: "Approved" | "Rejected", notes?: string) => {
    if (!selectedApproval) return
    decideApproval(selectedApproval, decision, notes)
  }, [selectedApproval, decideApproval])

  const decideBulk = useCallback((decision: "Approved" | "Rejected") => {
    const ids = [...bulkSelected].filter(id =>
      approvals.find(a => a.approval_id === id)?.status === "Pending"
    )
    if (ids.length === 0) return

    // Flush any in-flight pending commit before starting a new one
    flushPending()

    // Record previous statuses for undo
    const previousStatuses: Record<string, string> = {}
    ids.forEach(id => {
      const a = approvals.find(a => a.approval_id === id)
      if (a) previousStatuses[id] = a.status
    })

    // Optimistic update
    setApprovals(prev =>
      prev.map(a => ids.includes(a.approval_id) ? { ...a, status: decision } : a)
    )

    // Close panel if the selected item was in the batch
    if (selectedId && ids.includes(selectedId)) setSelectedId(null)

    // Clear selection
    setBulkSelected(new Set())

    pendingCommitRef.current = { approvalIds: ids, decision }

    startProgressCountdown()
    setUndo({ approvalIds: ids, previousStatuses, decision })

    undoTimerRef.current = setTimeout(() => {
      if (pendingCommitRef.current) {
        const { approvalIds, decision: d } = pendingCommitRef.current
        Promise.allSettled(approvalIds.map(id => commitDecision(id, d)))
        pendingCommitRef.current = null
      }
      setUndo(null)
      undoTimerRef.current = null
    }, UNDO_DURATION_MS)
  }, [bulkSelected, approvals, selectedId, commitDecision])

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

    // Revert all optimistic updates
    setApprovals(prev =>
      prev.map(a => undo.approvalIds.includes(a.approval_id)
        ? { ...a, status: undo.previousStatuses[a.approval_id] ?? a.status }
        : a
      )
    )

    // Reopen panel only for single-item undo
    if (undo.approvalIds.length === 1) setSelectedId(undo.approvalIds[0])
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
          onChange={(v) => { setStatusFilter(v); setSelectedId(null); setBulkSelected(new Set()) }}
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
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            {retryFn && (
              <button
                onClick={() => { retryFn(); setRetryFn(null); setError(null) }}
                style={{ fontSize: 11, fontWeight: 600, color: "var(--color-lime)", background: "none", border: "none", cursor: "pointer", padding: "0 2px" }}
              >
                Retry
              </button>
            )}
            <button
              onClick={() => { setError(null); setRetryFn(null) }}
              aria-label="Dismiss error"
              style={{ color: "inherit", opacity: 0.7, background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex" }}
            >
              <X size={13} />
            </button>
          </div>
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
                    <th className="px-3 py-2" style={{ width: 32 }}>
                      {pendingInView.length > 0 && (
                        <input
                          type="checkbox"
                          checked={allPendingSelected}
                          ref={(el) => { if (el) el.indeterminate = somePendingSelected }}
                          onChange={toggleSelectAll}
                          aria-label="Select all pending"
                          style={{ cursor: "pointer", accentColor: "var(--color-lime)" }}
                        />
                      )}
                    </th>
                    {/* Status column dropped — Pending is implied by tab filter,
                        resolved statuses live on the panel chip. Last column
                        is an action cell; it gets an explicit aria-label so
                        screen readers don't announce "blank column". */}
                    {[
                      { label: "Scene",        srOnly: false },
                      { label: "Studio",       srOnly: false },
                      { label: "Type",         srOnly: false },
                      { label: "Submitted by", srOnly: false },
                      { label: "Date",         srOnly: false },
                      { label: "Actions",      srOnly: true  },
                    ].map((h, i) => (
                      <th
                        key={i}
                        className="text-left px-3 py-2 font-medium"
                        style={{ fontSize: 11, color: "var(--color-text-muted)" }}
                        {...(h.srOnly ? { "aria-label": h.label } : {})}
                      >
                        {h.srOnly ? "" : h.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((approval, i) => {
                    const isSelected = approval.approval_id === selectedId
                    const rowColor = STUDIO_COLOR[approval.studio] ?? "var(--color-text-muted)"
                    const isPending = approval.status === "Pending"
                    // Row click opens the detail panel ONLY for resolved rows
                    // (read-only audit view). Pending rows expose explicit
                    // Approve / Reject… / View buttons in the actions cell —
                    // clicking the row body is inert there, which eliminates
                    // the "is this a preview or an action?" mental collision.
                    const rowClickable = !isPending
                    return (
                      <tr
                        key={approval.approval_id}
                        onClick={rowClickable ? () => selectRow(approval.approval_id) : undefined}
                        onKeyDown={rowClickable ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault()
                            selectRow(approval.approval_id)
                          }
                        } : undefined}
                        role="row"
                        aria-selected={isSelected}
                        tabIndex={rowClickable ? 0 : -1}
                        aria-label={rowClickable
                          ? `View ${CONTENT_TYPE_LABEL[approval.content_type] ?? approval.content_type} for scene ${approval.scene_id}`
                          : undefined
                        }
                        style={{
                          borderBottom: i < filtered.length - 1
                            ? "1px solid var(--color-border-subtle)"
                            : undefined,
                          background: isSelected
                            ? `color-mix(in srgb, ${rowColor} 8%, var(--color-elevated))`
                            : undefined,
                          cursor: rowClickable ? "pointer" : "default",
                          outline: "none",
                          transition: "background 120ms",
                        }}
                        className={rowClickable && !isSelected ? "hover:bg-[--color-elevated]" : ""}
                      >
                        <td
                          className="px-3 py-2.5"
                          style={{ width: 32 }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {approval.status === "Pending" && (
                            <input
                              type="checkbox"
                              checked={bulkSelected.has(approval.approval_id)}
                              onChange={() => toggleBulkSelect(approval.approval_id)}
                              aria-label={`Select ${approval.scene_id || "this item"}`}
                              style={{ cursor: "pointer", accentColor: "var(--color-lime)" }}
                            />
                          )}
                        </td>
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
                        <td
                          className="px-2 py-2"
                          style={{ textAlign: "right", whiteSpace: "nowrap" }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {isPending ? (
                            <div style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
                              <button
                                onClick={() => decideApproval(approval, "Approved")}
                                aria-label={`Approve ${approval.scene_id}`}
                                title="Approve without opening preview"
                                style={{
                                  padding: "3px 8px",
                                  borderRadius: 3,
                                  fontSize: 11,
                                  fontWeight: 500,
                                  cursor: "pointer",
                                  background: "color-mix(in srgb, var(--color-lime) 10%, transparent)",
                                  color: "var(--color-lime)",
                                  border: "1px solid color-mix(in srgb, var(--color-lime) 25%, transparent)",
                                }}
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => selectRow(approval.approval_id)}
                                aria-label={`Review ${approval.scene_id} before rejecting`}
                                title="Opens the preview panel — you need to write a reason to reject"
                                style={{
                                  padding: "3px 8px",
                                  borderRadius: 3,
                                  fontSize: 11,
                                  cursor: "pointer",
                                  background: "transparent",
                                  color: "var(--color-text-muted)",
                                  border: "1px solid var(--color-border)",
                                }}
                              >
                                Reject…
                              </button>
                              <button
                                onClick={() => selectRow(approval.approval_id)}
                                aria-label={`Preview ${approval.scene_id}`}
                                title="Open preview"
                                style={{
                                  padding: 3,
                                  borderRadius: 3,
                                  cursor: "pointer",
                                  background: "transparent",
                                  color: "var(--color-text-faint)",
                                  border: "1px solid transparent",
                                  display: "inline-flex",
                                  alignItems: "center",
                                }}
                                className="hover:text-[--color-text-muted] hover:border-[--color-border]"
                              >
                                <ChevronRight size={12} aria-hidden="true" />
                              </button>
                            </div>
                          ) : (
                            <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                              <span
                                style={{
                                  fontSize: 10,
                                  fontWeight: 500,
                                  padding: "1px 6px",
                                  borderRadius: 3,
                                  background: `color-mix(in srgb, ${STATUS_COLOR[approval.status] ?? "var(--color-text-muted)"} 14%, transparent)`,
                                  color: STATUS_COLOR[approval.status] ?? "var(--color-text-muted)",
                                  border: `1px solid color-mix(in srgb, ${STATUS_COLOR[approval.status] ?? "var(--color-text-muted)"} 25%, transparent)`,
                                }}
                              >
                                {approval.status}
                              </span>
                              <ChevronRight
                                size={12}
                                aria-hidden="true"
                                style={{
                                  color: isSelected ? rowColor : "var(--color-border)",
                                  transition: "color 150ms",
                                }}
                              />
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Bulk action bar — appears when rows are checked */}
          {bulkSelected.size > 0 && (
            <div
              style={{
                position: "sticky",
                bottom: 0,
                marginTop: 10,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 12px",
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                animation: "fadeIn 160ms var(--ease-out-expo) both",
              }}
            >
              <span style={{ fontSize: 12, color: "var(--color-text-muted)", flex: 1 }}>
                {bulkSelected.size} selected
              </span>
              <button
                onClick={() => decideBulk("Approved")}
                style={{
                  padding: "5px 12px",
                  borderRadius: 3,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                  background: "color-mix(in srgb, var(--color-lime) 12%, transparent)",
                  color: "var(--color-lime)",
                  border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
                }}
              >
                Approve {bulkSelected.size}
              </button>
              <button
                onClick={() => decideBulk("Rejected")}
                style={{
                  padding: "5px 12px",
                  borderRadius: 3,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                  background: "transparent",
                  color: "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                Reject {bulkSelected.size}
              </button>
              <button
                onClick={() => setBulkSelected(new Set())}
                aria-label="Clear selection"
                style={{ color: "var(--color-text-faint)", background: "none", border: "none", cursor: "pointer", padding: "0 4px", display: "flex", alignItems: "center" }}
              >
                <X size={12} />
              </button>
            </div>
          )}
        </div>

        {/* Panel wrapper — slides in with transform (no layout thrash) */}
        <div
          style={{
            width: 420,
            flexShrink: 0,
            overflow: "hidden",
            marginLeft: 12,
            transform: selectedApproval ? "translateX(0)" : "translateX(calc(100% + 12px))",
            opacity: selectedApproval ? 1 : 0,
            transition: "transform 260ms cubic-bezier(0.16, 1, 0.3, 1), opacity 260ms cubic-bezier(0.16, 1, 0.3, 1)",
            pointerEvents: selectedApproval ? "auto" : "none",
            position: selectedApproval ? "relative" : "absolute",
            right: selectedApproval ? undefined : 0,
          }}
        >
          {selectedApproval && (
            <ApprovalPanel
              key={selectedApproval.approval_id}
              approval={selectedApproval}
              onClose={() => setSelectedId(null)}
              onApprove={() => decide("Approved")}
              onReject={(reason) => decide("Rejected", reason)}
            />
          )}
        </div>
      </div>

      {/* Undo toast */}
      {undo && (
        <UndoToast
          decision={undo.decision}
          count={undo.approvalIds.length}
          progress={undoProgress}
          onUndo={handleUndo}
          onDismiss={handleDismissUndo}
        />
      )}
    </div>
  )
}
