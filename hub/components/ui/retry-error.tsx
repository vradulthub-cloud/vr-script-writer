import { AlertTriangle, RefreshCw } from "lucide-react"

interface RetryErrorProps {
  message: string
  onRetry?: () => void
  className?: string
}

export function RetryError({ message, onRetry, className }: RetryErrorProps) {
  return (
    <div
      className={`rounded p-3 text-xs flex items-start gap-2 ${className ?? ""}`}
      style={{
        background: "color-mix(in srgb, var(--color-err) 10%, var(--color-surface))",
        border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
        color: "var(--color-err)",
      }}
    >
      <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 1 }} />
      <div className="flex-1">
        <span>{message}</span>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1 ml-2 transition-colors hover:opacity-80"
            style={{ color: "var(--color-err)", fontWeight: 600 }}
          >
            <RefreshCw size={10} />
            Retry
          </button>
        )}
      </div>
    </div>
  )
}
