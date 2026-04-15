"use client"

interface FilterTabsProps {
  options: string[]
  value: string
  onChange: (v: string) => void
  counts?: Record<string, number>
}

export function FilterTabs({ options, value, onChange, counts }: FilterTabsProps) {
  return (
    <div className="flex gap-1 flex-wrap">
      {options.map((opt) => {
        const active = value === opt
        return (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className="px-2.5 py-1.5 rounded text-xs transition-colors"
            style={{
              background: active ? "var(--color-elevated)" : "transparent",
              color: active ? "var(--color-text)" : "var(--color-text-muted)",
              border: `1px solid ${active ? "var(--color-border)" : "transparent"}`,
            }}
          >
            {opt}
            {counts?.[opt] !== undefined && (
              <span style={{ color: "var(--color-text-faint)", marginLeft: 4 }}>
                {counts[opt]}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
