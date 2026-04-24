"use client"

import { useState, useEffect, useRef } from "react"
import { X } from "lucide-react"
import { StudioBadge } from "@/components/ui/studio-badge"
import { type Approval } from "@/lib/api"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { parseContentJson } from "./approval-utils"

// ─── Constants (local to panel) ───────────────────────────────────────────────

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

// ─── Approval Panel ───────────────────────────────────────────────────────────

export interface PanelProps {
  approval: Approval
  onClose: () => void
  onApprove: () => void
  onReject: (reason: string) => void
}

export function ApprovalPanel({ approval, onClose, onApprove, onReject }: PanelProps) {
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
