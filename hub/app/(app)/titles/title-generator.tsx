"use client"

import { useState, useEffect, useMemo } from "react"
import { api, type Treatment, type LocalTitleResult, type FluxLocalResult } from "@/lib/api"
import { ErrorAlert } from "@/components/ui/error-alert"
import { useIdToken } from "@/hooks/use-id-token"
import { PageHeader } from "@/components/ui/page-header"
const NAME_STUDIOS = ["VRA", "VRH"] as const
type NameStudio = typeof NAME_STUDIOS[number]

interface Props {
  idToken: string | undefined
}

// Local-only titles. PIL treatment library is the default pipeline; "Local AI"
// (FLUX + RMBG via Windows ComfyUI) is opt-in for free transparent AI output.
// The cloud (Ideogram V3) engine was retired — both UI and backend.
export function TitleGenerator({ idToken: serverIdToken }: Props) {
  const idToken = useIdToken(serverIdToken)
  const client = useMemo(() => api(idToken ?? null), [idToken])

  const [titleText, setTitleText] = useState("")

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

  // Load treatments on mount
  useEffect(() => {
    if (allTreatments.length > 0) return
    client.titles.treatments()
      .then(t => setAllTreatments(Array.isArray(t) ? t : []))
      .catch((e) => {
        console.warn("[titles] Failed to load treatments:", e)
        setAllTreatments([])
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Local AI state (FLUX + RMBG via Windows ComfyUI)
  const [fluxUseLora, setFluxUseLora] = useState(true)
  const [fluxSteps, setFluxSteps] = useState(4)
  const [fluxBgRemove, setFluxBgRemove] = useState<"rmbg2" | "none">("rmbg2")
  const [fluxResult, setFluxResult] = useState<FluxLocalResult | null>(null)
  const [fluxLoading, setFluxLoading] = useState(false)
  const [fluxError, setFluxError] = useState<string | null>(null)

  async function generateFlux() {
    if (!titleText) return
    setFluxLoading(true)
    setFluxError(null)
    setFluxResult(null)
    try {
      const data = await client.titles.fluxLocal({
        text: titleText,
        use_lora: fluxUseLora,
        steps: fluxSteps,
        seed: localSeed,
        bg_remove: fluxBgRemove,
      })
      if (data.error) {
        setFluxError(data.error)
      } else {
        setFluxResult(data)
      }
    } catch (e) {
      setFluxError(e instanceof Error ? e.message : "FLUX generation failed")
    } finally {
      setFluxLoading(false)
    }
  }

  function downloadFlux() {
    if (!fluxResult?.data_url) return
    const a = document.createElement("a")
    a.href = fluxResult.data_url
    a.download = `flux-${titleText.toLowerCase().replace(/\s+/g, "-").slice(0, 30)}-${fluxResult.seed}.png`
    a.click()
  }

  // Model name generator state
  const [mnName, setMnName] = useState("")
  const [mnStudio, setMnStudio] = useState<NameStudio>("VRH")
  const [mnLoading, setMnLoading] = useState(false)
  const [mnError, setMnError] = useState<string | null>(null)
  const [mnDataUrl, setMnDataUrl] = useState<string | null>(null)

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

  return (
    <div>
      <PageHeader
        title="Titles"
        eyebrow="Local · PIL treatments"
      />
      <div className="flex gap-6" style={{ alignItems: "flex-start" }}>
        {/* ── Left — inputs ── */}
        <div style={{ width: 280, flexShrink: 0 }}>
        <div className="flex flex-col gap-3">
          {/* Title text */}
          <div>
            <label htmlFor="title-text-input" className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Title text</label>
            <input
              id="title-text-input"
              type="text"
              value={titleText}
              onChange={e => setTitleText(e.target.value)}
              onKeyDown={e => e.key === "Enter" && generateLocal()}
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
          )}
        </div>

        {/* Generate button */}
        <button
          onClick={generateLocal}
          disabled={localLoading || !titleText}
          className="w-full mt-4 px-3 py-2 rounded text-xs font-semibold transition-colors"
          style={{
            background: localLoading ? "var(--color-elevated)" : "var(--color-lime)",
            color: localLoading ? "var(--color-text-muted)" : "var(--color-lime-ink)",
            cursor: localLoading ? "wait" : "pointer",
            opacity: (!titleText && !localLoading) ? 0.5 : 1,
          }}
        >
          {localLoading
            ? "Generating…"
            : !titleText
              ? "Enter title to continue"
              : `Generate ${localN} Local PNGs`}
        </button>
      </div>

      {/* ── Right — output ── */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 24 }}>
        {localError && <ErrorAlert className="mb-3">{localError}</ErrorAlert>}
        {localLoading && (
          <div className="rounded flex items-center justify-center"
            style={{ height: 240, border: "1px solid var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-muted)", fontSize: 12 }}
          >
            Rendering {localN} treatments…
          </div>
        )}
        {!localLoading && localResults.length === 0 && !localError && (
          <div className="rounded flex flex-col items-center justify-center gap-2"
            style={{ height: 240, border: "1px dashed var(--color-border)", color: "var(--color-text-faint)", fontSize: 12, textAlign: "center", padding: "0 24px" }}
          >
            <span style={{ fontSize: 18, opacity: 0.4 }}>◈</span>
            <span style={{ fontWeight: 600, color: "var(--color-text-muted)", fontSize: 13 }}>No treatments rendered</span>
            <span>Choose a treatment count and Generate — 690+ styles available locally.</span>
          </div>
        )}
        {localResults.length > 0 && !localLoading && (
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

        {/* ── Local AI (FLUX + RMBG) ── */}
        <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
            Local AI · FLUX + RMBG
          </p>
          <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 12 }}>
            Generates via FLUX.1 Schnell on the Windows box, strips background with RMBG-2.0. Uses the title text from above. Requires ComfyUI running.
          </p>

          <div className="flex gap-2 items-end mb-3 flex-wrap">
            {/* LoRA toggle */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Style LoRA</label>
              <div className="flex gap-1">
                {([[true, "On"], [false, "Off"]] as const).map(([val, label]) => (
                  <button key={String(val)} onClick={() => setFluxUseLora(val)}
                    className="px-2.5 py-1 rounded text-xs transition-colors"
                    style={{
                      background: fluxUseLora === val ? "var(--color-elevated)" : "transparent",
                      color: fluxUseLora === val ? "var(--color-text)" : "var(--color-text-muted)",
                      border: `1px solid ${fluxUseLora === val ? "var(--color-border)" : "transparent"}`,
                    }}
                  >{label}</button>
                ))}
              </div>
            </div>

            {/* Steps */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Steps</label>
              <div className="flex gap-1">
                {[2, 4, 6, 8].map(n => (
                  <button key={n} onClick={() => setFluxSteps(n)}
                    className="px-2 py-1 rounded text-xs transition-colors"
                    style={{
                      background: fluxSteps === n ? "var(--color-elevated)" : "transparent",
                      color: fluxSteps === n ? "var(--color-text)" : "var(--color-text-muted)",
                      border: `1px solid ${fluxSteps === n ? "var(--color-border)" : "transparent"}`,
                    }}
                  >{n}</button>
                ))}
              </div>
            </div>

            {/* BG remove */}
            <div>
              <label className="block mb-1" style={{ fontSize: 11, color: "var(--color-text-muted)" }}>BG remove</label>
              <div className="flex gap-1">
                {([["rmbg2", "RMBG-2"], ["none", "Off"]] as const).map(([val, label]) => (
                  <button key={val} onClick={() => setFluxBgRemove(val)}
                    className="px-2.5 py-1 rounded text-xs transition-colors"
                    style={{
                      background: fluxBgRemove === val ? "var(--color-elevated)" : "transparent",
                      color: fluxBgRemove === val ? "var(--color-text)" : "var(--color-text-muted)",
                      border: `1px solid ${fluxBgRemove === val ? "var(--color-border)" : "transparent"}`,
                    }}
                  >{label}</button>
                ))}
              </div>
            </div>

            <button
              onClick={generateFlux}
              disabled={fluxLoading || !titleText}
              className="px-3 py-1.5 rounded text-xs font-semibold transition-colors"
              style={{
                background: fluxLoading ? "var(--color-elevated)" : "var(--color-lime)",
                color: fluxLoading ? "var(--color-text-muted)" : "var(--color-lime-ink)",
                cursor: fluxLoading ? "wait" : "pointer",
                opacity: (!titleText && !fluxLoading) ? 0.5 : 1,
              }}
            >
              {fluxLoading ? "Rendering…" : !titleText ? "Enter title" : "Generate FLUX"}
            </button>
          </div>

          {fluxError && <ErrorAlert className="mb-2 text-xs">{fluxError}</ErrorAlert>}

          {fluxLoading && (
            <div className="rounded flex items-center justify-center"
              style={{ height: 220, border: "1px solid var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-muted)", fontSize: 12 }}
            >
              FLUX inference on the Windows box — typically 8–20s
            </div>
          )}

          {fluxResult && fluxResult.data_url && !fluxLoading && (
            <div style={{ maxWidth: 720 }}>
              <div className="rounded overflow-hidden mb-1.5"
                style={{
                  border: "1px solid var(--color-border)",
                  background: "repeating-conic-gradient(#1a1a1a 0% 25%, #111 0% 50%) 0 0 / 16px 16px",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={fluxResult.data_url} alt={`FLUX: ${titleText}`} style={{ width: "100%", display: "block" }} />
              </div>
              <p style={{ fontSize: 10, color: "var(--color-text-faint)", marginBottom: 6 }}>
                seed {fluxResult.seed} · {fluxUseLora ? "LoRA on" : "no LoRA"} · {fluxSteps} steps · {fluxBgRemove === "rmbg2" ? "RMBG-2" : "no BG removal"}
              </p>
              <button
                onClick={downloadFlux}
                className="px-2 py-1 rounded text-xs transition-colors"
                style={{ background: "var(--color-lime)", color: "var(--color-lime-ink)", fontWeight: 600 }}
              >
                Download
              </button>
            </div>
          )}
        </div>

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
