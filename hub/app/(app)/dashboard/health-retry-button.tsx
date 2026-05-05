"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"
import { RefreshCw } from "lucide-react"

// Lives next to the HealthBadge "Connection lost" indicator. Triggers a
// router refresh so server components re-fetch — the cheapest reliable
// recovery path before forcing a full page reload.
export function HealthRetryButton() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  return (
    <button
      type="button"
      onClick={() => startTransition(() => router.refresh())}
      disabled={pending}
      aria-label="Retry connection"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        marginLeft: 4,
        padding: "2px 6px",
        background: "transparent",
        border: "1px solid color-mix(in srgb, var(--color-err) 40%, transparent)",
        borderRadius: 4,
        color: "var(--color-err)",
        fontSize: 11,
        fontWeight: 600,
        cursor: pending ? "wait" : "pointer",
        opacity: pending ? 0.6 : 1,
        transition: "opacity 120ms ease, background 120ms ease",
      }}
    >
      <RefreshCw size={10} style={pending ? { animation: "spin 0.8s linear infinite" } : undefined} />
      {pending ? "Retrying" : "Retry"}
    </button>
  )
}
