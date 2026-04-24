"use client"

import { useState, useRef, useEffect } from "react"

interface EditableParagraphProps {
  text: string
  index: number
  studioColor: string
  onSave: (index: number, newText: string) => void
  onRegenerate?: (index: number, feedback: string) => Promise<string | null>
}

export function EditableParagraph({
  text,
  index,
  studioColor,
  onSave,
  onRegenerate,
}: EditableParagraphProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)
  const [feedback, setFeedback] = useState("")
  const [regenerating, setRegenerating] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setDraft(text)
  }, [text])

  useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus()
      taRef.current.style.height = "auto"
      taRef.current.style.height = taRef.current.scrollHeight + "px"
    }
  }, [editing])

  async function handleRegenerate() {
    if (!onRegenerate) return
    setRegenerating(true)
    setRegenError(null)
    try {
      const next = await onRegenerate(index, feedback.trim())
      if (next != null) {
        setDraft(next)
        if (taRef.current) {
          taRef.current.style.height = "auto"
          taRef.current.style.height = taRef.current.scrollHeight + "px"
        }
      }
    } catch (e) {
      setRegenError(e instanceof Error ? e.message : "Regeneration failed")
    } finally {
      setRegenerating(false)
    }
  }

  if (editing) {
    return (
      <div className="mb-3">
        <textarea
          ref={taRef}
          value={draft}
          onChange={e => {
            setDraft(e.target.value)
            e.target.style.height = "auto"
            e.target.style.height = e.target.scrollHeight + "px"
          }}
          className="w-full px-3 py-2 rounded text-xs outline-none resize-none"
          style={{
            background: "var(--color-elevated)",
            border: `1px solid ${studioColor}`,
            color: "var(--color-text)",
            lineHeight: 1.7,
            minHeight: 60,
          }}
        />
        {onRegenerate && (
          <div className="mt-1.5">
            <input
              type="text"
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              placeholder="Optional nudge for regenerate (e.g. 'more tension, less dialogue')"
              className="w-full px-2.5 py-1 rounded text-xs outline-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>
        )}
        {regenError && (
          <p style={{ fontSize: 10, color: "var(--color-err)", marginTop: 4 }}>{regenError}</p>
        )}
        <div className="flex gap-2 mt-1.5 flex-wrap">
          <button
            onClick={() => { onSave(index, draft); setEditing(false); setFeedback("") }}
            disabled={regenerating}
            className="px-2.5 py-1 rounded text-xs font-semibold"
            style={{
              background: regenerating ? "var(--color-elevated)" : "var(--color-lime)",
              color: regenerating ? "var(--color-text-muted)" : "var(--color-lime-ink)",
              cursor: regenerating ? "wait" : "pointer",
            }}
          >
            Save
          </button>
          {onRegenerate && (
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="px-2.5 py-1 rounded text-xs"
              style={{
                color: "var(--color-text)",
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                cursor: regenerating ? "wait" : "pointer",
              }}
              title="Ask Claude to rewrite just this paragraph"
            >
              {regenerating ? "Regenerating…" : "↻ Regenerate"}
            </button>
          )}
          <button
            onClick={() => { setDraft(text); setEditing(false); setFeedback(""); setRegenError(null) }}
            disabled={regenerating}
            className="px-2.5 py-1 rounded text-xs"
            style={{ color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <p
      onClick={() => setEditing(true)}
      title="Click to edit"
      className="mb-3 rounded px-2 -mx-2 transition-colors cursor-text group"
      style={{
        fontSize: 13,
        color: "var(--color-text)",
        lineHeight: 1.7,
      }}
      onMouseEnter={e => (e.currentTarget.style.background = "var(--color-elevated)")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >
      {text}
    </p>
  )
}
