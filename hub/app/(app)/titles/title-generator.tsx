"use client"

import { useState, useEffect, useMemo } from "react"
import { api, API_BASE_URL, type Treatment, type LocalTitleResult } from "@/lib/api"
import { ErrorAlert } from "@/components/ui/error-alert"
import { STUDIO_COLOR } from "@/lib/studio-colors"
import { useIdToken } from "@/hooks/use-id-token"
import { StudioSelector, STUDIOS } from "@/components/ui/studio-selector"
import { PageHeader } from "@/components/ui/page-header"
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
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [engine, setEngine] = useState<"cloud" | "local">("cloud")

  const [titleText, setTitleText] = useState("")
  const [style, setStyle] = useState<Style>("cinematic")
  const [studio, setStudio] = useState("")
  const [variations, setVariations] = useState(1)

  // Local mode state
  const [localMode, setLocalMode] = useState<"random" | "auto" | "pick">("random")
  const [localN, setLocalN] = useState(6)
  const [localSeed, setLocalSeed] = useState(0)
  const [featuredOnly, setFeaturedOnly] = useState(true)
  const [treatmentFilter, setTreatmentFilter] = useState("")
  const [selectedTreatment, setSelectedTreatment] = useState("")
  const [allTreatments, setAllTreatments] = useState<Treatment[]>([])
  const [localResults, setLocalResults] = useState<LocalTitleResult[]>([])
  const [localLoading, setLocalLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  // Load treatments on first switch to local mode
  useEffect(() => {
    if (engine !== "local" || allTreatments.length > 0) return
    client.titles.treatments().then(setAllTreatments).catch((e) => {
      console.warn("[titles] Failed to load treatments:", e)
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engine])

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
      const data = await client.titles.modelName({ name: mnName.trim(), studio: mnStudio })
      if (data.error) throw new Error(data.error)
      setMnDataUrl(data.data_url)
    } catch (e) {
      setMnError(e instanceof Error ? e.message : "Render failed")
    } finally {
      setMnLoading(false)
    }
  }

  async function generateLocal() {
    if (!titleText) return
    setLocalLoading(true)
    setLocalError(null)
    setLocalResults([])
    try {
      const body: {
        text: string
        treatments?: string[]
        n: number
        seed: number
        auto_match?: boolean
      } = {
        text: titleText,
        n: localN,
        seed: localSeed,
      }
      if (localMode === "pick" && selectedTreatment) {
        body.treatments = Array(localN).fill(selectedTreatment)
      } else if (localMode === "auto") {
        body.auto_match = true
      }
      const data = await client.titles.local(body)
      setLocalResults(data)
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "Generation failed")
    } finally {
      setLocalLoading(false)
    }
  }

  async function refineLocal(idx: number, prompt: string) {
    const r = localResults[idx]
    if (!r || !prompt) return
    try {
      const result = await client.titles.refine({
        text: titleText,
        treatment_name: r.treatment_name,
        refine_prompt: prompt,
        seed: localSeed,
      })
      setLocalResults(prev => prev.map((item, i) => i === idx ? result : item))
    } catch (e) {
      setLocalResults(prev => prev.map((item, i) =>
        i === idx ? { ...item, error: e instanceof Error ? e.message : "Refine failed" } : item
      ))
    }
  }

  function downloadLocalImage(dataUrl: string, treatmentName: string) {
    const a = document.createElement("a")
    a.href = dataUrl
    a.download = `title-${titleText.toLowerCase().replace(/\s+/g, "-").slice(0, 30)}-${treatmentName}.png`
    a.click()
  }

  const filteredTreatments = allTreatments.filter(t => {
    if (featuredOnly && !t.featured) return false
    if (treatmentFilter && !t.name.toLowerCase().includes(treatmentFilter.toLowerCase())) return false
    return true
  })

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
    <div>
      <PageHeader
        title="Titles"
        eyebrow={engine === "cloud" ? "Cloud · Ideogram V3" : "Local · PIL treatments"}
        studioAccent={studio}
      />
      <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
        {/* ── Left — inputs ── */}
        <div style={{ width: 280, flexShrink: 0 }}>
        {/* Engine toggle */}
        <div className="flex gap-1 mb-4">
          {(["cloud", "local"] as const).map(e => (
            <button
              key={e}
              onClick={() => {
                if (e === engine) return
                setEngine(e)
                // Clear the opposite engine's results/errors so a stale
                // response from the other engine isn't presented as current.
                if (e === "cloud") {
                  setLocalResults([])
                  setLocalError(null)
                  setLocalLoading(false)
                } else {
                  setResults([])
                  setError(null)
                  setLoading(false)
                }
              }}
              className="px-3 py-1.5 rounded text-xs transition-colors capitalize"
              style={{
                background: engine === e ? "var(--color-elevated)" : "transparent",
                color: engine === e ? "var(--color-text)" : "var(--color-text-muted)",
                border: `1px solid ${engine === e ? "var(--color-border)" : "transparent"}`,
              }}
            >
              {e === "cloud" ? "Cloud" : "Local"}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-3">
          {/* Title text (shared) */}
          <div>
            <label htmlFor="title-text-input" className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Title text</label>
            <input
              id="title-text-input"
              type="text"
              value={titleText}
              onChange={e => setTitleText(e.target.value)}
              onKeyDown={e => e.key === "Enter" && (engine === "cloud" ? generate() : generateLocal())}
              placeholder="Enter scene title…"
              className="w-full px-2.5 py-1.5 rounded text-xs"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
            <p style={{ fontSize: 10, color: titleText.length > 55 ? "var(--color-warn)" : "var(--color-text-faint)", marginTop: 3 }}>
              {titleText.length}/55 chars — fits cleanly on card at ≤55
            </p>
          </div>

          {engine === "cloud" ? (
            <>
              {/* Style */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Style</label>
                <div className="flex gap-1">
                  {STYLES.map(s => (
                    <button key={s} onClick={() => setStyle(s)} title={STYLE_DESCRIPTIONS[s]}
                      className="px-2.5 py-1.5 rounded text-xs transition-colors capitalize"
                      style={{
                        background: style === s ? "var(--color-elevated)" : "transparent",
                        color: style === s ? "var(--color-text)" : "var(--color-text-muted)",
                        border: `1px solid ${style === s ? "var(--color-border)" : "transparent"}`,
                      }}
                    >{s}</button>
                  ))}
                </div>
                <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4 }}>{STYLE_DESCRIPTIONS[style]}</p>
              </div>

              {/* Studio */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Studio <span style={{ color: "var(--color-text-faint)" }}>(optional)</span></label>
                <div className="flex gap-1 flex-wrap">
                  <button
                    onClick={() => setStudio("")}
                    className="px-2 py-1 rounded text-xs transition-colors"
                    style={{
                      background: !studio ? "var(--color-elevated)" : "transparent",
                      color: !studio ? "var(--color-text)" : "var(--color-text-faint)",
                      border: `1px solid ${!studio ? "var(--color-border)" : "transparent"}`,
                    }}
                  >None</button>
                  <StudioSelector value={studio} onChange={setStudio} />
                </div>
              </div>

              {/* Variations slider (1-20) */}
              <div>
                <label htmlFor="title-variations-input" className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                  Variations: <span style={{ color: "var(--color-text)" }}>{variations}</span>
                </label>
                <input
                  id="title-variations-input"
                  aria-label={`Variations: ${variations}`}
                  type="range" min={1} max={20} value={variations}
                  onChange={e => setVariations(Number(e.target.value))}
                  className="w-full"
                  style={{ accentColor: "var(--color-lime)" }}
                />
              </div>
            </>
          ) : (
            <>
              {/* Local mode selector */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Mode</label>
                <div className="flex gap-1">
                  {([["random", "Random mix"], ["auto", "Auto-match"], ["pick", "Pick one"]] as const).map(([key, label]) => (
                    <button key={key} onClick={() => setLocalMode(key as "random" | "auto" | "pick")}
                      className="px-2 py-1 rounded text-xs transition-colors"
                      style={{
                        background: localMode === key ? "var(--color-elevated)" : "transparent",
                        color: localMode === key ? "var(--color-text)" : "var(--color-text-muted)",
                        border: `1px solid ${localMode === key ? "var(--color-border)" : "transparent"}`,
                      }}
                    >{label}</button>
                  ))}
                </div>
              </div>

              {/* Variations (1-12) */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                  Variations: <span style={{ color: "var(--color-text)" }}>{localN}</span>
                </label>
                <input
                  type="range" min={1} max={12} value={localN}
                  onChange={e => setLocalN(Number(e.target.value))}
                  className="w-full" style={{ accentColor: "var(--color-lime)" }}
                />
              </div>

              {/* Seed */}
              <div>
                <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Seed <span style={{ color: "var(--color-text-faint)" }}>(0 = random)</span></label>
                <input
                  type="number" min={0} max={999999} value={localSeed}
                  onChange={e => setLocalSeed(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 rounded text-xs"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                />
              </div>

              {/* Treatment picker (for "pick" mode) */}
              {localMode === "pick" && (
                <>
                  <div>
                    <label className="flex items-center gap-2 mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                      <input type="checkbox" checked={featuredOnly} onChange={e => setFeaturedOnly(e.target.checked)} />
                      Featured only ({allTreatments.filter(t => t.featured).length})
                    </label>
                    <input
                      type="text" value={treatmentFilter}
                      onChange={e => setTreatmentFilter(e.target.value)}
                      placeholder="Filter treatments..."
                      className="w-full px-2.5 py-1.5 rounded text-xs outline-none mb-1"
                      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                    />
                    <select
                      value={selectedTreatment}
                      onChange={e => setSelectedTreatment(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded text-xs"
                      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)", maxHeight: 200 }}
                    >
                      <option value="">Select treatment...</option>
                      {filteredTreatments.map(t => (
                        <option key={t.name} value={t.name}>{t.name}{t.featured ? " ★" : ""}</option>
                      ))}
                    </select>
                    <p style={{ fontSize: 10, color: filteredTreatments.length === 0 ? "var(--color-text-muted)" : "var(--color-text-faint)", marginTop: 2 }}>
                      {filteredTreatments.length === 0
                        ? allTreatments.length === 0
                          ? "Loading treatments…"
                          : "No treatments match — try clearing filters"
                        : `${filteredTreatments.length} of ${allTreatments.length} treatments`}
                    </p>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Generate button */}
        <button
          onClick={engine === "cloud" ? generate : generateLocal}
          disabled={(engine === "cloud" ? loading : localLoading) || !titleText}
          className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
          style={{
            background: (engine === "cloud" ? loading : localLoading) ? "var(--color-elevated)" : "var(--color-lime)",
            color: (engine === "cloud" ? loading : localLoading) ? "var(--color-text-muted)" : "var(--color-lime-ink)",
            cursor: (engine === "cloud" ? loading : localLoading) ? "wait" : "pointer",
            opacity: (!titleText && !(engine === "cloud" ? loading : localLoading)) ? 0.5 : 1,
          }}
        >
          {(engine === "cloud" ? loading : localLoading)
            ? "Generating…"
            : !titleText
              ? "Enter title to continue"
              : engine === "cloud"
                ? variations > 1 ? `Generate ${variations} Variations` : "Generate Title Card"
                : `Generate ${localN} Local PNGs`}
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
            className="rounded flex flex-col items-center justify-center gap-2"
            style={{
              height: 240,
              border: "1px dashed var(--color-border)",
              color: "var(--color-text-faint)",
              fontSize: 12,
              textAlign: "center",
              padding: "0 24px",
            }}
          >
            <span style={{ fontSize: 18, opacity: 0.4 }}>◈</span>
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", fontSize: 13 }}>No card yet</span>
            <span>Enter a title, pick a style, and Generate — cloud routes to ComfyUI, local to your machine.</span>
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
                    color: "var(--color-lime-ink)",
                  }}
                >
                  Download{successResults.length > 1 ? ` v${i + 1}` : ""}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── Local mode results ── */}
        {engine === "local" && localError && <ErrorAlert className="mb-3">{localError}</ErrorAlert>}
        {engine === "local" && localLoading && (
          <div className="rounded flex items-center justify-center"
            style={{ height: 240, border: "1px solid var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-muted)", fontSize: 12 }}
          >
            Rendering {localN} treatments…
          </div>
        )}
        {engine === "local" && !localLoading && localResults.length === 0 && !localError && (
          <div className="rounded flex flex-col items-center justify-center gap-2"
            style={{ height: 240, border: "1px dashed var(--color-border)", color: "var(--color-text-faint)", fontSize: 12, textAlign: "center", padding: "0 24px" }}
          >
            <span style={{ fontSize: 18, opacity: 0.4 }}>◈</span>
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", fontSize: 13 }}>No treatments rendered</span>
            <span>Choose a treatment count and Generate — 690+ styles available locally.</span>
          </div>
        )}
        {engine === "local" && localResults.length > 0 && !localLoading && (
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
            {localResults.map((r, i) => (
              <div key={i}>
                {r.error ? (
                  <>
                    <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 4 }}>{r.treatment_name}</p>
                    <ErrorAlert className="text-xs mb-1">{r.error}</ErrorAlert>
                  </>
                ) : (
                  <>
                    <div className="rounded overflow-hidden mb-1.5"
                      style={{
                        border: "1px solid var(--color-border)",
                        background: "repeating-conic-gradient(#1a1a1a 0% 25%, #111 0% 50%) 0 0 / 16px 16px",
                      }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={r.data_url} alt={`${r.treatment_name}: ${titleText}`} style={{ width: "100%", display: "block" }} />
                    </div>
                    <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 4 }}>{r.treatment_name}</p>
                    <div className="flex gap-1.5 mb-1.5">
                      <button
                        onClick={() => downloadLocalImage(r.data_url, r.treatment_name)}
                        className="px-2 py-1 rounded text-xs transition-colors"
                        style={{ background: "var(--color-lime)", color: "var(--color-lime-ink)", fontWeight: 600 }}
                      >
                        Download
                      </button>
                    </div>
                    <RefineInput onRefine={(prompt) => refineLocal(i, prompt)} />
                  </>
                )}
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
                        ? s === "VRA" ? "var(--color-vra)" : "var(--color-vrh)"
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
              <label htmlFor="model-name-input" className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Model name</label>
              <input
                id="model-name-input"
                type="text"
                value={mnName}
                onChange={e => setMnName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && generateModelName()}
                placeholder="e.g. Emma Rosie"
                className="w-full px-2.5 py-1.5 rounded text-xs"
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
                color: mnLoading ? "var(--color-text-muted)" : "var(--color-lime-ink)",
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
                style={{ background: "var(--color-lime)", color: "var(--color-lime-ink)" }}
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
    </div>
  )
}


// Small inline refine input
function RefineInput({ onRefine }: { onRefine: (prompt: string) => void }) {
  const [val, setVal] = useState("")
  return (
    <div className="flex gap-1">
      <input
        type="text" value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="Refine: gold, darker…"
        className="flex-1 px-2 py-0.5 rounded outline-none"
        style={{ fontSize: 10, background: "var(--color-base)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
        onKeyDown={(e) => { if (e.key === "Enter" && val) { onRefine(val); setVal("") } }}
      />
      <button
        onClick={() => { if (val) { onRefine(val); setVal("") } }}
        className="px-1.5 py-0.5 rounded"
        style={{ fontSize: 10, color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
      >
        Apply
      </button>
    </div>
  )
}
