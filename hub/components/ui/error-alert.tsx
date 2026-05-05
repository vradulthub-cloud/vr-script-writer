import { AlertTriangle, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

interface ErrorAlertProps {
  children: React.ReactNode
  className?: string
  // Optional retry handler — when provided, renders a "Retry" affordance so
  // recoverable failures (network, transient server errors) don't strand the
  // user on a dead-end red box.
  onRetry?: () => void
  retryLabel?: string
}

export function ErrorAlert({ children, className, onRetry, retryLabel = "Retry" }: ErrorAlertProps) {
  return (
    <div
      className={cn("rounded p-3 text-xs flex items-start gap-2", className)}
      style={{
        background: "color-mix(in srgb, var(--color-err) 10%, var(--color-surface))",
        border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
        color: "var(--color-err)",
      }}
    >
      <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 1 }} />
      <div className="flex-1 min-w-0">{children}</div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1 transition-colors hover:opacity-80"
          style={{ color: "var(--color-err)", fontWeight: 600, flexShrink: 0 }}
        >
          <RefreshCw size={11} />
          {retryLabel}
        </button>
      )}
    </div>
  )
}
