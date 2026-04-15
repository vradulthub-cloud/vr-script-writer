"use client"

import { useState } from "react"
import { API_BASE_URL } from "@/lib/api"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"

const STUDIOS = ["FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"]
const NAME_STUDIOS = ["VRA", "VRH"] as const
type NameStudio = typeof NAME_STUDIOS[number]
const STYLES = ["cinematic", "bold", "minimal"] as const
type Style = typeof STYLES[number]

const STYLE_DESCRIPTIONS: Record<Style, string> = {
  cinematic: "Dark, moody atmosphere — film poster depth",
  bold:      "High contrast, heavy typography — editorial punch",
  minimal:   "Clean layout, refined type — restrained palette",
}

interface TitleResult {
  url: string | null
  error: string | null
}

interface Props {
  idToken: string | undefined
}

export function TitleGenerator({ idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)

  const [titleText, setTitleText] = useState("")
  const [style, setStyle] = useState<Style>("cinematic")
  const [studio, setStudio] = useState("")
  const [variations, setVariations] = useState(1)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<TitleResult[]>([])

  // Model name generator state
  const [mnName, setMnName] = useState("")
  const [mnStudio, setMnStudio] = useState<NameStudio>("VRH")
  const [mnLoading, setMnLoading] = useState(false)
  const [mnError, setMnError] = useState<string | null>(null)
  const [mnDataUrl, setMnDataUrl] = useState<string | null>(null)

  const activeStudioColor = studio ? STUDIO_COLOR[studio] : undefined

  async function generate() {
    if (!titleText) return
    setLoading(true)
    setError(null)
    setResults([])

    try {
      const res = await fetch(`${API_BASE_URL}/api/titles/cloud`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          text: titleText,
          style,
          studio: studio || undefined,
          n: variations,
        }),
      })

      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`${res.status}: ${text}`)
      }

      const data = await res.json() as TitleResult[]
      setResults(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed")
    } finally {
      setLoading(false)
    }
  }

  async function generateModelName() {
    if (!mnName.trim()) return
    setMnLoading(true)
    setMnError(null)
    setMnDataUrl(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/titles/model-name`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({ name: mnName.trim(), studio: mnStudio }),
      })
      if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => "")}`)
      const data = await res.json() as { data_url: string; error?: string }
      if (data.error) throw new Error(data.error)
      setMnDataUrl(data.data_url)
    } catch (e) {
      setMnError(e instanceof Error ? e.message : "Render failed")
    } finally {
      setMnLoading(false)
    }
  }

  function downloadModelName() {
    if (!mnDataUrl) return
    const a = document.createElement("a")
    a.href = mnDataUrl
    a.download = `${mnStudio}-${mnName.trim().replace(/\s+/g, "")}.png`
    a.click()
  }

  function downloadImage(url: string, index: number) {
    const a = document.createElement("a")
    a.href = url
    a.download = `title-${titleText.toLowerCase().replace(/\s+/g, "-").slice(0, 40)}${variations > 1 ? `-v${index + 1}` : ""}.png`
    a.click()
  }

  const successResults = results.filter(r => r.url)
  const errorResults   = results.filter(r => r.error)

  return (
    <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
      {/* ── Left — inputs ── */}
      <div style={{ width: 280, flexShrink: 0 }}>
        <div className="flex flex-col gap-3">

          {/* Title text */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Title text</label>
            <input
              type="text"
              value={titleText}
              onChange={e => setTitleText(e.target.value)}
              onKeyDown={e => e.key === "Enter" && generate()}
              placeholder="Enter scene title…"
              className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
          </div>

          {/* Style */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Style</label>
            <div className="flex gap-1">
              {STYLES.map(s => (
                <button
                  key={s}
                  onClick={() => setStyle(s)}
                  title={STYLE_DESCRIPTIONS[s]}
                  className="px-2.5 py-1.5 rounded text-xs transition-colors capitalize"
                  style={{
                    background: style === s ? "var(--color-elevated)" : "transparent",
                    color: style === s ? "var(--color-text)" : "var(--color-text-muted)",
                    border: `1px solid ${style === s ? "var(--color-border)" : "transparent"}`,
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4 }}>
              {STYLE_DESCRIPTIONS[style]}
            </p>
          </div>

          {/* Studio (optional) */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              Studio <span style={{ color: "var(--color-text-faint)" }}>(optional)</span>
            </label>
            <div className="flex gap-1 flex-wrap">
              {["", ...STUDIOS].map(s => {
                const active = studio === s
                const color = s ? STUDIO_COLOR[s] : "var(--color-text-muted)"
                return (
                  <button
                    key={s || "none"}
                    onClick={() => setStudio(s)}
                    className="px-2 py-1 rounded text-xs transition-colors"
                    style={{
                      background: active
                        ? s ? `color-mix(in srgb, ${color} 20%, transparent)` : "var(--color-elevated)"
                        : "transparent",
                      color: active ? (s ? color : "var(--color-text)") : "var(--color-text-faint)",
                      border: `1px solid ${active
                        ? s ? `color-mix(in srgb, ${color} 35%, transparent)` : "var(--color-border)"
                        : "transparent"}`,
                    }}
                  >
                    {s === "" ? "None" :
                     s === "FuckPassVR" ? "FPVR" :
                     s === "NaughtyJOI" ? "NJOI" :
                     s === "VRHush" ? "VRH" : "VRA"}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Variations */}
          <div>
            <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
              Variations
            </label>
            <div className="flex gap-1">
              {[1, 2, 3, 4].map(n => (
                <button
                  key={n}
                  onClick={() => setVariations(n)}
                  className="px-3 py-1.5 rounded text-xs transition-colors"
                  style={{
                    background: variations === n ? "var(--color-elevated)" : "transparent",
                    color: variations === n ? "var(--color-text)" : "var(--color-text-muted)",
                    border: `1px solid ${variations === n ? "var(--color-border)" : "transparent"}`,
                  }}
                >
                  {n}×
                </button>
              ))}
            </div>
            {variations > 1 && (
              <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4 }}>
                Runs {variations} parallel requests — takes longer
              </p>
            )}
          </div>
        </div>

        {/* Generate button */}
        <button
          onClick={generate}
          disabled={loading || !titleText}
          className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
          style={{
            background: loading ? "var(--color-elevated)" : "var(--color-lime)",
            color: loading ? "var(--color-text-muted)" : "#0d0d0d",
            cursor: loading ? "wait" : "pointer",
            opacity: (!titleText && !loading) ? 0.5 : 1,
          }}
        >
          {loading
            ? `Generating ${variations > 1 ? `${variations} variations` : ""}…`
            : !titleText
              ? "Enter title to continue"
              : variations > 1
                ? `Generate ${variations} Variations`
                : "Generate Title Card"}
        </button>
      </div>

      {/* ── Right — output ── */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 24 }}>
        {error && <ErrorAlert className="mb-3">{error}</ErrorAlert>}

        {loading && (
          <div
            className="rounded flex items-center justify-center"
            style={{
              height: 240,
              border: "1px solid var(--color-border)",
              background: "var(--color-surface)",
              color: "var(--color-text-muted)",
              fontSize: 12,
            }}
          >
            <span>Generating{variations > 1 ? ` ${variations} variations` : ""}…</span>
          </div>
        )}

        {!successResults.length && !loading && (
          <div
            className="rounded flex items-center justify-center"
            style={{
              height: 240,
              border: "1px dashed var(--color-border)",
              color: "var(--color-text-faint)",
              fontSize: 12,
            }}
          >
            Title card{variations > 1 ? "s" : ""} will appear here
          </div>
        )}

        {/* Error results from individual requests */}
        {errorResults.length > 0 && (
          <div className="mb-3">
            {errorResults.map((r, i) => (
              <ErrorAlert key={i} className="mb-1 text-xs">{r.error}</ErrorAlert>
            ))}
          </div>
        )}

        {/* Image gallery */}
        {successResults.length > 0 && !loading && (
          <div
            className={successResults.length > 1 ? "grid gap-3" : ""}
            style={successResults.length > 1 ? { gridTemplateColumns: "repeat(2, 1fr)" } : undefined}
          >
            {successResults.map((result, i) => (
              <div key={i}>
                <div
                  className="rounded overflow-hidden mb-2"
                  style={{
                    border: `1px solid ${activeStudioColor
                      ? `color-mix(in srgb, ${activeStudioColor} 30%, var(--color-border))`
                      : "var(--color-border)"}`,
                  }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={result.url!}
                    alt={`Title card${successResults.length > 1 ? ` v${i + 1}` : ""}: ${titleText}`}
                    loading="lazy"
                    style={{ width: "100%", display: "block" }}
                  />
                </div>
                <button
                  onClick={() => downloadImage(result.url!, i)}
                  className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                  style={{
                    background: "var(--color-lime)",
                    color: "#0d0d0d",
                  }}
                >
                  Download{successResults.length > 1 ? ` v${i + 1}` : ""}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── Model Name Generator ── */}
        <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
            Model Name Generator
          </p>

          {/* Controls row */}
          <div className="flex gap-2 items-end mb-3">
            {/* Studio toggle */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio</label>
              <div className="flex gap-1">
                {NAME_STUDIOS.map(s => (
                  <button
                    key={s}
                    onClick={() => setMnStudio(s)}
                    className="px-3 py-1.5 rounded text-xs transition-colors font-semibold"
                    style={{
                      background: mnStudio === s ? "var(--color-elevated)" : "transparent",
                      color: mnStudio === s
                        ? s === "VRA" ? "#ec4899" : "#8b5cf6"
                        : "var(--color-text-faint)",
                      border: `1px solid ${mnStudio === s ? "var(--color-border)" : "transparent"}`,
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Name input */}
            <div style={{ flex: 1 }}>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Model name</label>
              <input
                type="text"
                value={mnName}
                onChange={e => setMnName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && generateModelName()}
                placeholder="e.g. Emma Rosie"
                className="w-full px-2.5 py-1.5 rounded text-xs outline-none"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
            </div>

            {/* Generate button */}
            <button
              onClick={generateModelName}
              disabled={mnLoading || !mnName.trim()}
              className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
              style={{
                background: mnLoading ? "var(--color-elevated)" : "var(--color-lime)",
                color: mnLoading ? "var(--color-text-muted)" : "#0d0d0d",
                cursor: mnLoading ? "wait" : "pointer",
                opacity: (!mnName.trim() && !mnLoading) ? 0.5 : 1,
                whiteSpace: "nowrap",
                marginBottom: 1,
              }}
            >
              {mnLoading ? "Rendering…" : "Generate"}
            </button>
          </div>

          {mnError && <ErrorAlert className="mb-3">{mnError}</ErrorAlert>}

          {/* Result */}
          {mnDataUrl && (
            <div>
              {/* Transparent bg preview — dark checkerboard */}
              <div
                className="rounded overflow-hidden mb-2"
                style={{
                  border: "1px solid var(--color-border)",
                  background: "repeating-conic-gradient(#1a1a1a 0% 25%, #111 0% 50%) 0 0 / 16px 16px",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={mnDataUrl}
                  alt={`${mnStudio} name card: ${mnName}`}
                  style={{ width: "100%", display: "block" }}
                />
              </div>
              <button
                onClick={downloadModelName}
                className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                style={{ background: "var(--color-lime)", color: "#0d0d0d" }}
              >
                Download {mnStudio} — {mnName}
              </button>
            </div>
          )}

          {!mnDataUrl && !mnLoading && (
            <div
              className="rounded flex items-center justify-center"
              style={{
                height: 80,
                border: "1px dashed var(--color-border)",
                color: "var(--color-text-faint)",
                fontSize: 12,
              }}
            >
              Name card will appear here
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
