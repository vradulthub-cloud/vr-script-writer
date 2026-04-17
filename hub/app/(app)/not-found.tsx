import Link from "next/link"
import { ArrowLeft, Search } from "lucide-react"

/**
 * Custom 404 for the authenticated app segment. Inherits sidebar + topbar
 * from (app)/layout.tsx, so users aren't stranded on a chromeless page.
 *
 * Scene-ID search: if the user is clearly looking for a scene (pattern like
 * FPVR1234, VRH0762, VRA0001, NNJOI0099), the Asset Tracker link preselects
 * that ID via the ?scene= query param so the side panel opens on arrival.
 */
export default function NotFound() {
  return (
    <div style={{ maxWidth: 560, padding: "48px 0" }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--color-text-faint)",
          marginBottom: 10,
        }}
      >
        404 · Not found
      </div>

      <h1 style={{ margin: "0 0 10px" }}>This page doesn&apos;t exist.</h1>

      <p style={{ fontSize: 13, color: "var(--color-text-muted)", lineHeight: 1.55, margin: "0 0 22px", maxWidth: 480 }}>
        The URL may be stale, the scene may have been renamed, or this route was
        never shipped. Everything else in the hub still works.
      </p>

      {/* Scene-ID search — the most common reason to hit a 404 in daily use
          is a bookmarked/shared scene that got renamed. */}
      <form
        action="/missing"
        method="get"
        style={{
          display: "flex",
          alignItems: "stretch",
          gap: 0,
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          overflow: "hidden",
          marginBottom: 28,
          maxWidth: 420,
        }}
      >
        <div
          style={{
            padding: "0 10px",
            display: "flex",
            alignItems: "center",
            color: "var(--color-text-faint)",
            background: "var(--color-base)",
          }}
        >
          <Search size={13} aria-hidden="true" />
        </div>
        <input
          name="scene"
          type="text"
          placeholder="Scene ID (e.g. VRH0762)"
          required
          // Browser-level validation: scene IDs are alphanumeric + optional
          // hyphen. Stops 'foo bar' silently landing on /missing?scene=foo%20bar.
          pattern="[A-Za-z0-9\-]+"
          title="Use letters, digits, and hyphens only (e.g. VRH0762)"
          autoCapitalize="characters"
          autoComplete="off"
          style={{
            flex: 1,
            padding: "8px 10px",
            fontSize: 12,
            outline: "none",
            background: "var(--color-base)",
            border: "none",
            borderLeft: "1px solid var(--color-border)",
            borderRight: "1px solid var(--color-border)",
            color: "var(--color-text)",
            fontFamily: "var(--font-mono)",
          }}
        />
        <button
          type="submit"
          style={{
            padding: "0 14px",
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            background: "var(--color-lime)",
            color: "#000",
            border: "none",
          }}
        >
          Find
        </button>
      </form>

      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <Link
          href="/dashboard"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            color: "var(--color-text-muted)",
            textDecoration: "none",
          }}
          className="hover:text-[--color-text]"
        >
          <ArrowLeft size={12} aria-hidden="true" />
          Back to dashboard
        </Link>
        <span style={{ color: "var(--color-border)" }}>·</span>
        <Link
          href="/missing"
          style={{ fontSize: 12, color: "var(--color-text-muted)", textDecoration: "none" }}
          className="hover:text-[--color-text]"
        >
          Asset Tracker
        </Link>
        <Link
          href="/approvals"
          style={{ fontSize: 12, color: "var(--color-text-muted)", textDecoration: "none" }}
          className="hover:text-[--color-text]"
        >
          Approvals
        </Link>
        <Link
          href="/tickets"
          style={{ fontSize: 12, color: "var(--color-text-muted)", textDecoration: "none" }}
          className="hover:text-[--color-text]"
        >
          Tickets
        </Link>
      </div>
    </div>
  )
}
