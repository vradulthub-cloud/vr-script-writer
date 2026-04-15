"use client"

interface FilterTabsProps {
  options: string[]
  value: string
  onChange: (v: string) => void
  counts?: Record<string, number>
}

export function FilterTabs({ options, value, onChange, counts }: FilterTabsProps) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {options.map((opt) => {
        const active = value === opt
        return (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className="px-3 py-1.5 rounded transition-colors"
            style={{
              fontSize: 12,
              fontWeight: active ? 600 : 400,
              background: active ? "var(--color-elevated)" : "transparent",
              color: active ? "var(--color-text)" : "var(--color-text-muted)",
              border: `1px solid ${active ? "var(--color-border)" : "transparent"}`,
            }}
          >
            {opt}
            {counts?.[opt] !== undefined && (
              <span
                className="tabular-nums"
                style={{
                  color: active ? "var(--color-lime)" : "var(--color-text-faint)",
                  marginLeft: 5,
                  fontWeight: 600,
                }}
              >
                {counts[opt]}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
