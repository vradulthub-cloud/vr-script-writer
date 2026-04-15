"use client"

import { useState, useEffect } from "react"
import { api, type Ticket } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { STUDIO_COLOR } from "@/lib/studio-colors"

const CONTENT_TYPES = ["Script", "Description", "Compilation", "Title", "Tags", "Categories"]
const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]

interface Props {
  idToken: string | undefined
}

export function ApprovalSubmit({ idToken: serverToken }: Props) {
  const idToken = useIdToken(serverToken)
  const client = api(idToken ?? null)

  const [contentType, setContentType] = useState("Script")
  const [sceneId, setSceneId] = useState("")
  const [studio, setStudio] = useState("FuckPassVR")
  const [content, setContent] = useState("")
  const [notes, setNotes] = useState("")
  const [linkedTicket, setLinkedTicket] = useState("")
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submitMsg, setSubmitMsg] = useState("")

  useEffect(() => {
    client.tickets.list({ status: "In Progress" }).then(setTickets).catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function submit() {
    if (!sceneId || !content) return
    setSubmitting(true)
    setSubmitMsg("")
    try {
      const approval = await client.approvals.create({
        scene_id: sceneId,
        studio,
        content_type: contentType.toLowerCase(),
        content_json: JSON.stringify({ content, notes }),
        notes: linkedTicket ? `Linked: ${linkedTicket}` : notes,
      })
      setSubmitMsg(`Submitted: ${approval.approval_id}`)
      setSceneId("")
      setContent("")
      setNotes("")
      setLinkedTicket("")
    } catch (e) {
      setSubmitMsg(e instanceof Error ? e.message : "Submit failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="flex flex-col gap-4">
        {/* Content type */}
        <div>
          <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Content type</label>
          <div className="flex gap-1 flex-wrap">
            {CONTENT_TYPES.map(t => (
              <button
                key={t}
                onClick={() => setContentType(t)}
                className="px-2.5 py-1 rounded text-xs transition-colors"
                style={{
                  background: contentType === t ? "var(--color-elevated)" : "transparent",
                  color: contentType === t ? "var(--color-text)" : "var(--color-text-muted)",
                  border: `1px solid ${contentType === t ? "var(--color-border)" : "transparent"}`,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Studio */}
        <div>
          <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio</label>
          <div className="flex gap-1 flex-wrap">
            {STUDIOS.map(s => {
              const color = STUDIO_COLOR[s]
              return (
                <button
                  key={s}
                  onClick={() => setStudio(s)}
                  className="px-2 py-1 rounded text-xs transition-colors"
                  style={{
                    background: studio === s ? `color-mix(in srgb, ${color} 20%, transparent)` : "transparent",
                    color: studio === s ? color : "var(--color-text-muted)",
                    border: `1px solid ${studio === s ? `color-mix(in srgb, ${color} 35%, transparent)` : "var(--color-border)"}`,
                  }}
                >
                  {s === "FuckPassVR" ? "FPVR" : s === "NaughtyJOI" ? "NJOI" : s === "VRHush" ? "VRH" : "VRA"}
                </button>
              )
            })}
          </div>
        </div>

        {/* Scene ID */}
        <div>
          <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Scene ID</label>
          <input
            type="text"
            value={sceneId}
            onChange={e => setSceneId(e.target.value)}
            placeholder="e.g. VRH0758"
            className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>

        {/* Content */}
        <div>
          <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Content</label>
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={6}
            placeholder="Paste the content to submit for approval..."
            className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-y"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)", lineHeight: 1.6 }}
          />
        </div>

        {/* Notes */}
        <div>
          <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Notes <span style={{ color: "var(--color-text-faint)" }}>(optional)</span></label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
            placeholder="Any context for the reviewer..."
            className="w-full px-2.5 py-1.5 rounded text-xs outline-none resize-none"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>

        {/* Linked ticket */}
        {tickets.length > 0 && (
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Link to ticket</label>
            <select
              value={linkedTicket}
              onChange={e => setLinkedTicket(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            >
              <option value="">— None —</option>
              {tickets.map(t => (
                <option key={t.ticket_id} value={t.ticket_id}>{t.ticket_id} — {t.title}</option>
              ))}
            </select>
          </div>
        )}

        {/* Submit */}
        <div className="flex items-center gap-3">
          <button
            onClick={submit}
            disabled={submitting || !sceneId || !content}
            className="px-4 py-2 rounded text-xs font-semibold transition-colors"
            style={{
              background: "var(--color-lime)",
              color: "#0d0d0d",
              opacity: (submitting || !sceneId || !content) ? 0.5 : 1,
            }}
          >
            {submitting ? "Submitting..." : "Submit for Approval"}
          </button>
          {submitMsg && (
            <span style={{ fontSize: 11, color: submitMsg.startsWith("Submitted") ? "var(--color-ok)" : "var(--color-err)" }}>
              {submitMsg}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
