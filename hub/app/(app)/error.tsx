"use client"

import { useEffect } from "react"
import Link from "next/link"
import { ArrowLeft, AlertTriangle } from "lucide-react"

/**
 * Route-segment error boundary for the authenticated app.
 *
 * Catches any uncaught error thrown during server-component rendering or
 * client-component hydration below (app)/. Without this, a single crash
 * in a page tree takes out the whole shell (sidebar, topbar, nav) and
 * shows the bare Next.js overlay in dev / a blank page in prod.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("[hub] route error:", error)
  }, [error])

  return (
    <div style={{ maxWidth: 560, padding: "48px 0" }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--color-err)",
          marginBottom: 10,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <AlertTriangle size={12} aria-hidden="true" />
        Something went wrong
      </div>

      <h1 style={{ margin: "0 0 10px" }}>This page failed to load.</h1>

      <p style={{ fontSize: 13, color: "var(--color-text-muted)", lineHeight: 1.55, margin: "0 0 22px", maxWidth: 480 }}>
        The rest of the hub is fine — only this view crashed. Try again, or jump to another tab from the sidebar.
      </p>

      {error.digest && (
        <p style={{ fontSize: 11, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)", marginBottom: 22 }}>
          Error ID: {error.digest}
        </p>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <button
          onClick={reset}
          style={{
            padding: "8px 14px",
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            background: "var(--color-lime)",
            color: "#000",
            border: "none",
            borderRadius: 6,
          }}
        >
          Try again
        </button>
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
      </div>
    </div>
  )
}
