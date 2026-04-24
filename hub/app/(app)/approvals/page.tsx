import Link from "next/link"

/**
 * Approvals workflow is paused — the tab in /tickets and the dashboard
 * triage card were removed because the team isn't using approvals yet.
 *
 * The route stays mounted (this file, plus approval-list and
 * approval-submit alongside it) so we can flip it back on without
 * resurrecting deleted code: re-add the Approvals tab in
 * /tickets/tickets-tabs.tsx and the Approvals subsection in
 * /dashboard/triage-feed.tsx, both of which already import the
 * components correctly. The API client + backend untouched.
 */
export const dynamic = "force-dynamic"

export default function ApprovalsPage() {
  return (
    <div style={{ maxWidth: 560, padding: "32px 0" }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        Approvals
      </div>
      <h1
        style={{
          margin: "6px 0 12px",
          fontSize: 30,
          fontWeight: 400,
          letterSpacing: "-0.02em",
          color: "var(--color-text)",
          fontFamily: "var(--font-display-hero)",
        }}
      >
        Paused
      </h1>
      <p style={{ fontSize: 14, lineHeight: 1.55, color: "var(--color-text-muted)", marginBottom: 8 }}>
        The approvals workflow is turned off for now — no approvals queue is
        being shown across the app.
      </p>
      <p style={{ fontSize: 13, lineHeight: 1.55, color: "var(--color-text-faint)" }}>
        The route + components are still here so an admin can re-enable
        approvals later without re-implementing them. In the meantime,
        edits land directly on the sheet via{" "}
        <Link href="/scripts" style={{ color: "var(--color-lime)", textDecoration: "none" }}>Scripts</Link>{" "}
        or{" "}
        <Link href="/descriptions" style={{ color: "var(--color-lime)", textDecoration: "none" }}>Descriptions</Link>.
      </p>
    </div>
  )
}
