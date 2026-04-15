import { cn } from "@/lib/utils"

interface ErrorAlertProps {
  children: React.ReactNode
  className?: string
}

export function ErrorAlert({ children, className }: ErrorAlertProps) {
  return (
    <div
      className={cn("rounded p-3 text-xs", className)}
      style={{
        background: "color-mix(in srgb, var(--color-err) 10%, var(--color-surface))",
        border: "1px solid color-mix(in srgb, var(--color-err) 30%, transparent)",
        color: "var(--color-err)",
      }}
    >
      {children}
    </div>
  )
}
