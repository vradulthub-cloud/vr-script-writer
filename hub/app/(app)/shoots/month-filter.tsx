"use client"

import { useMemo } from "react"

interface MonthFilterProps {
  value: string
  onChange: (v: string) => void
}

export function MonthFilter({ value, onChange }: MonthFilterProps) {
  const options = useMemo(() => {
    const now = new Date()
    const items: { key: string; label: string }[] = []
    for (let offset = -6; offset <= 6; offset++) {
      const d = new Date(now.getFullYear(), now.getMonth() + offset, 1)
      const y = d.getFullYear()
      const m = d.getMonth() + 1
      const key = `${y}-${String(m).padStart(2, "0")}`
      const label = d.toLocaleDateString(undefined, { month: "short", year: "2-digit" })
      items.push({ key, label })
    }
    return items
  }, [])

  return (
    <label
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        fontSize: 11, color: "var(--color-text-muted)",
      }}
    >
      Month
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          fontSize: 11, padding: "3px 6px", borderRadius: 4,
          background: "var(--color-surface)", color: "var(--color-text)",
          border: "1px solid var(--color-border)",
          cursor: "pointer",
        }}
      >
        <option value="">Default (this + next)</option>
        {options.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
      </select>
    </label>
  )
}
