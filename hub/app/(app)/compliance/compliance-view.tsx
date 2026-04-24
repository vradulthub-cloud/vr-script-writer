"use client"

import { useRef, useState } from "react"
import {
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  FolderOpen,
  Loader2,
  RefreshCw,
  Upload,
  X,
} from "lucide-react"
import { api, type ComplianceShoot, type CompliancePrepareResult } from "@/lib/api"

// ─── Studio colors ────────────────────────────────────────────────────────────

const STUDIO_COLOR: Record<string, string> = {
  FuckPassVR: "#f97316",
  VRHush:     "#8b5cf6",
  VRAllure:   "#ec4899",
  NaughtyJOI: "#3b82f6",
}

function studioColor(studio: string) {
  return STUDIO_COLOR[studio] ?? "var(--color-lime)"
}

// ─── Photo slot definition ────────────────────────────────────────────────────

interface PhotoSlot {
  id: string
  label: string  // used as filename
  display: string
  talent: "female" | "male"
  category: "id" | "bunny"
  required: boolean
}

function buildSlots(female: string, male: string): PhotoSlot[] {
  const slots: PhotoSlot[] = [
    {
      id: `${female.replace(/ /g, "")}-id-front`,
      label: `${female.replace(/ /g, "")}-id-front.jpg`,
      display: `${female} — IDs Front`,
      talent: "female", category: "id", required: true,
    },
    {
      id: `${female.replace(/ /g, "")}-id-back`,
      label: `${female.replace(/ /g, "")}-id-back.jpg`,
      display: `${female} — IDs Back`,
      talent: "female", category: "id", required: true,
    },
    {
      id: `${female.replace(/ /g, "")}-bunny`,
      label: `${female.replace(/ /g, "")}-bunny-ear.jpg`,
      display: `${female} — Bunny Ear`,
      talent: "female", category: "bunny", required: true,
    },
  ]
  if (male) {
    slots.push(
      {
        id: `${male.replace(/ /g, "")}-id-front`,
        label: `${male.replace(/ /g, "")}-id-front.jpg`,
        display: `${male} — IDs Front`,
        talent: "male", category: "id", required: true,
      },
      {
        id: `${male.replace(/ /g, "")}-id-back`,
        label: `${male.replace(/ /g, "")}-id-back.jpg`,
        display: `${male} — IDs Back`,
        talent: "male", category: "id", required: true,
      },
      {
        id: `${male.replace(/ /g, "")}-bunny`,
        label: `${male.replace(/ /g, "")}-bunny-ear.jpg`,
        display: `${male} — Bunny Ear`,
        talent: "male", category: "bunny", required: true,
      },
    )
  }
  return slots
}

// ─── Captured photo state ─────────────────────────────────────────────────────

interface CapturedPhoto {
  slotId: string
  label: string
  file: File
  preview: string
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StepDot({ n, current, done }: { n: number; current: number; done: boolean }) {
  const active = n === current
  const bg = done ? "var(--color-lime)" : active ? "var(--color-lime)" : "var(--color-elevated)"
  const opacity = done || active ? 1 : 0.4
  return (
    <div
      style={{
        width: 28, height: 28, borderRadius: "50%",
        background: bg, opacity,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700,
        color: done || active ? "#000" : "var(--color-text-faint)",
        flexShrink: 0,
        transition: "background 0.2s",
      }}
    >
      {done ? <CheckCircle2 size={14} /> : n}
    </div>
  )
}

function StatusBadge({ shoot }: { shoot: ComplianceShoot }) {
  if (shoot.is_complete) {
    return (
      <span style={{
        fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
        padding: "3px 8px", borderRadius: 4,
        background: "rgba(190,214,47,0.15)", color: "var(--color-lime)",
        textTransform: "uppercase",
      }}>Complete</span>
    )
  }
  if (shoot.pdfs_ready && shoot.photos_uploaded > 0) {
    return (
      <span style={{
        fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
        padding: "3px 8px", borderRadius: 4,
        background: "rgba(251,191,36,0.12)", color: "#fbbf24",
        textTransform: "uppercase",
      }}>In Progress</span>
    )
  }
  if (shoot.pdfs_ready) {
    return (
      <span style={{
        fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
        padding: "3px 8px", borderRadius: 4,
        background: "rgba(99,102,241,0.12)", color: "#818cf8",
        textTransform: "uppercase",
      }}>Docs Ready</span>
    )
  }
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
      padding: "3px 8px", borderRadius: 4,
      background: "rgba(255,255,255,0.06)", color: "var(--color-text-faint)",
      textTransform: "uppercase",
    }}>Not Started</span>
  )
}

function CameraButton({
  slot,
  captured,
  onCapture,
}: {
  slot: PhotoSlot
  captured?: CapturedPhoto
  onCapture: (file: File, preview: string) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)

  function handleFile(file: File) {
    const url = URL.createObjectURL(file)
    onCapture(file, url)
  }

  return (
    <div style={{ position: "relative" }}>
      {/* Hidden inputs */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: "none" }}
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = "" }}
      />
      <input
        ref={uploadRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = "" }}
      />

      <div
        style={{
          border: captured ? "2px solid var(--color-lime)" : "2px dashed var(--color-border)",
          borderRadius: 12,
          overflow: "hidden",
          background: "var(--color-elevated)",
          position: "relative",
          aspectRatio: "4/3",
          cursor: "pointer",
        }}
        onClick={() => inputRef.current?.click()}
      >
        {captured ? (
          /* Preview */
          <>
            <img
              src={captured.preview}
              alt={slot.display}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
            <div style={{
              position: "absolute", bottom: 0, left: 0, right: 0,
              background: "linear-gradient(transparent, rgba(0,0,0,0.7))",
              padding: "12px 10px 8px",
              display: "flex", justifyContent: "space-between", alignItems: "flex-end",
            }}>
              <span style={{ fontSize: 11, color: "#fff", fontWeight: 600 }}>
                {slot.display}
              </span>
              <button
                style={{
                  background: "rgba(255,255,255,0.15)", border: "none",
                  borderRadius: 6, padding: "4px 8px", cursor: "pointer",
                  color: "#fff", fontSize: 11, display: "flex", alignItems: "center", gap: 4,
                }}
                onClick={e => { e.stopPropagation(); inputRef.current?.click() }}
              >
                <RefreshCw size={11} /> Retake
              </button>
            </div>
            <div style={{
              position: "absolute", top: 8, right: 8,
              background: "var(--color-lime)", borderRadius: "50%",
              width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <CheckCircle2 size={13} color="#000" />
            </div>
          </>
        ) : (
          /* Empty state */
          <div style={{
            height: "100%", display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            gap: 8, padding: 16,
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: "50%",
              background: "rgba(255,255,255,0.06)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Camera size={22} color="var(--color-text-muted)" />
            </div>
            <span style={{ fontSize: 12, color: "var(--color-text-muted)", textAlign: "center", lineHeight: 1.3 }}>
              {slot.display}
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                style={{
                  background: "var(--color-lime)", border: "none", borderRadius: 6,
                  padding: "6px 12px", cursor: "pointer", color: "#000",
                  fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", gap: 4,
                }}
                onClick={e => { e.stopPropagation(); inputRef.current?.click() }}
              >
                <Camera size={12} /> Camera
              </button>
              <button
                style={{
                  background: "transparent",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6, padding: "6px 12px", cursor: "pointer",
                  color: "var(--color-text-muted)",
                  fontSize: 11, display: "flex", alignItems: "center", gap: 4,
                }}
                onClick={e => { e.stopPropagation(); uploadRef.current?.click() }}
              >
                <Upload size={12} /> Upload
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  initialShoots: ComplianceShoot[]
  initialDate: string
  idToken: string | undefined
  loadError: string | null
}

type WizardStep = "select" | "docs" | "photos" | "upload"

export function ComplianceView({ initialShoots, initialDate, idToken, loadError }: Props) {
  const client = api(idToken)

  // Date + shoot list state
  const [date, setDate] = useState(initialDate)
  const [shoots, setShoots] = useState<ComplianceShoot[]>(initialShoots)
  const [loading, setLoading] = useState(false)

  // Wizard state
  const [selected, setSelected] = useState<ComplianceShoot | null>(null)
  const [step, setStep] = useState<WizardStep>("select")

  // Docs step state
  const [preparing, setPreparing] = useState(false)
  const [prepResult, setPrepResult] = useState<CompliancePrepareResult | null>(null)
  const [prepError, setPrepError] = useState<string | null>(null)

  // Photos step state
  const [photos, setPhotos] = useState<CapturedPhoto[]>([])

  // Upload step state
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ uploaded: string[]; errors: string[]; mega_paths: string[] } | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ status: string; message: string } | null>(null)

  const slots = selected ? buildSlots(selected.female_talent, selected.male_talent) : []

  // ── Date fetch ────────────────────────────────────────────────────────

  async function loadDate(d: string) {
    setLoading(true)
    try {
      const data = await client.compliance.shoots(d)
      setShoots(data)
    } catch (e) {
      setShoots([])
    } finally {
      setLoading(false)
    }
  }

  function handleDateChange(d: string) {
    setDate(d)
    void loadDate(d)
  }

  // ── Select shoot ──────────────────────────────────────────────────────

  function selectShoot(shoot: ComplianceShoot) {
    setSelected(shoot)
    setStep("docs")
    setPrepResult(null)
    setPrepError(null)
    setPhotos([])
    setUploadResult(null)
    setSyncResult(null)
    // If Drive folder already exists, pre-populate prep result state
    if (shoot.drive_folder_id) {
      setPrepResult({
        folder_id: shoot.drive_folder_id,
        folder_url: shoot.drive_folder_url!,
        folder_name: shoot.drive_folder_name!,
        female_pdf_id: "",
        male_pdf_id: "",
        male_known: false,
        dates_filled: false,
        message: "Folder already exists",
      })
    }
  }

  function exitWizard() {
    setSelected(null)
    setStep("select")
  }

  // ── Prepare docs ──────────────────────────────────────────────────────

  async function prepareDocs() {
    if (!selected) return
    setPreparing(true)
    setPrepError(null)
    try {
      const r = await client.compliance.prepare(selected.shoot_id)
      setPrepResult(r)
      // Refresh shoot list to get updated pdfs_ready
      void loadDate(date)
    } catch (e) {
      setPrepError(e instanceof Error ? e.message : "Prepare failed")
    } finally {
      setPreparing(false)
    }
  }

  // ── Photo capture ─────────────────────────────────────────────────────

  function capturePhoto(slot: PhotoSlot, file: File, preview: string) {
    setPhotos(prev => {
      const without = prev.filter(p => p.slotId !== slot.id)
      return [...without, { slotId: slot.id, label: slot.label, file, preview }]
    })
  }

  function removePhoto(slotId: string) {
    setPhotos(prev => prev.filter(p => p.slotId !== slotId))
  }

  // ── Upload ────────────────────────────────────────────────────────────

  async function uploadAll() {
    if (!selected || photos.length === 0) return
    setUploading(true)
    setUploadResult(null)
    try {
      const r = await client.compliance.uploadPhotos(
        selected.shoot_id,
        photos.map(p => ({ file: p.file, label: p.label })),
        selected.scene_id || undefined,
        selected.studio || undefined,
      )
      setUploadResult(r)
      void loadDate(date)
    } catch (e) {
      setUploadResult({ uploaded: [], errors: [e instanceof Error ? e.message : "Upload failed"], mega_paths: [] })
    } finally {
      setUploading(false)
    }
  }

  async function syncMega() {
    if (!selected || !selected.scene_id || !selected.studio) return
    setSyncing(true)
    setSyncResult(null)
    try {
      const r = await client.compliance.megaSync(selected.shoot_id, selected.scene_id, selected.studio)
      setSyncResult(r)
    } catch (e) {
      setSyncResult({ status: "error", message: e instanceof Error ? e.message : "Sync failed" })
    } finally {
      setSyncing(false)
    }
  }

  // ── Studio color for active shoot ─────────────────────────────────────

  const accent = selected ? studioColor(selected.studio) : "var(--color-lime)"

  // ─────────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────────

  const STEPS: { key: WizardStep; label: string }[] = [
    { key: "select", label: "Select" },
    { key: "docs",   label: "Docs" },
    { key: "photos", label: "Photos" },
    { key: "upload", label: "Finish" },
  ]
  const stepIdx = STEPS.findIndex(s => s.key === step)

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)", padding: "0 0 80px" }}>

      {/* ── Header ── */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        padding: "14px 20px",
        display: "flex", alignItems: "center", gap: 16,
      }}>
        {selected ? (
          <button
            onClick={exitWizard}
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              color: "var(--color-text-muted)", padding: "4px 8px 4px 0",
              display: "flex", alignItems: "center", gap: 4, fontSize: 13,
            }}
          >
            <ChevronLeft size={16} /> All Shoots
          </button>
        ) : null}

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)", letterSpacing: "0.02em" }}>
            {selected ? `${selected.female_talent}${selected.male_talent ? ` × ${selected.male_talent}` : ""}` : "Compliance"}
          </div>
          {selected && (
            <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 1 }}>
              {new Date(selected.shoot_date + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
              {selected.studio && (
                <span style={{ marginLeft: 8, color: accent }}>{selected.studio}</span>
              )}
            </div>
          )}
        </div>

        {/* Step indicator */}
        {selected && (
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {STEPS.map((s, i) => (
              <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <StepDot n={i + 1} current={stepIdx + 1} done={i < stepIdx} />
                {i < STEPS.length - 1 && (
                  <div style={{ width: 16, height: 1, background: "var(--color-border)" }} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Step: Select ── */}
      {step === "select" && (
        <div style={{ padding: "16px 16px 0" }}>

          {/* Date picker */}
          <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10 }}>
            <label style={{ fontSize: 11, color: "var(--color-text-faint)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", flexShrink: 0 }}>
              Shoot Date
            </label>
            <input
              type="date"
              value={date}
              onChange={e => handleDateChange(e.target.value)}
              style={{
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                borderRadius: 8, padding: "8px 12px",
                color: "var(--color-text)", fontSize: 14,
                flex: 1, cursor: "pointer",
              }}
            />
          </div>

          {loadError && (
            <div style={{
              background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8, padding: "10px 14px", marginBottom: 16,
              fontSize: 13, color: "#f87171",
            }}>
              {loadError}
            </div>
          )}

          {loading ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-text-faint)", fontSize: 13, padding: 20 }}>
              <Loader2 size={16} className="animate-spin" /> Loading…
            </div>
          ) : shoots.length === 0 ? (
            <div style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 12, padding: 32,
              textAlign: "center", color: "var(--color-text-faint)", fontSize: 14,
            }}>
              No BG shoots for {new Date(date + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {shoots.map(shoot => {
                const sc = studioColor(shoot.studio)
                return (
                  <button
                    key={shoot.shoot_id}
                    onClick={() => selectShoot(shoot)}
                    style={{
                      background: "var(--color-surface)",
                      border: `1px solid var(--color-border)`,
                      borderLeft: `4px solid ${sc}`,
                      borderRadius: 12,
                      padding: "16px 18px",
                      cursor: "pointer",
                      textAlign: "left",
                      width: "100%",
                      display: "flex", alignItems: "center", gap: 14,
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
                        <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)" }}>
                          {shoot.female_talent}
                        </span>
                        {shoot.male_talent && (
                          <>
                            <span style={{ fontSize: 13, color: "var(--color-text-faint)" }}>×</span>
                            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--color-text-muted)" }}>
                              {shoot.male_talent}
                            </span>
                          </>
                        )}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 11, color: sc, fontWeight: 600 }}>{shoot.studio}</span>
                        {shoot.scene_id && (
                          <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontFamily: "var(--font-mono)" }}>
                            {shoot.scene_id}
                          </span>
                        )}
                      </div>
                      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <StatusBadge shoot={shoot} />
                        {shoot.pdfs_ready && (
                          <span style={{ fontSize: 10, color: "var(--color-text-faint)", display: "flex", alignItems: "center", gap: 3 }}>
                            <FileText size={10} /> PDFs ready
                          </span>
                        )}
                        {shoot.photos_uploaded > 0 && (
                          <span style={{ fontSize: 10, color: "var(--color-text-faint)", display: "flex", alignItems: "center", gap: 3 }}>
                            <Camera size={10} /> {shoot.photos_uploaded} photo{shoot.photos_uploaded !== 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronRight size={18} color="var(--color-text-faint)" />
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Step: Docs ── */}
      {step === "docs" && selected && (
        <div style={{ padding: 16 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 16 }}>
            Step 1 — Paperwork
          </h2>

          {/* Drive folder card */}
          <div style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: 12, padding: 18, marginBottom: 14,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <FolderOpen size={18} color={accent} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>Drive Legal Folder</div>
                {prepResult?.folder_name && (
                  <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
                    {prepResult.folder_name}
                  </div>
                )}
              </div>
            </div>

            {prepResult ? (
              <>
                <div style={{ marginBottom: 14 }}>
                  {prepResult.message && (
                    <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 10, lineHeight: 1.4 }}>
                      {prepResult.message}
                    </p>
                  )}
                  <a
                    href={prepResult.folder_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: "flex", alignItems: "center", gap: 6,
                      background: accent,
                      color: "#000",
                      border: "none", borderRadius: 10,
                      padding: "14px 20px",
                      fontSize: 15, fontWeight: 700, cursor: "pointer",
                      textDecoration: "none", justifyContent: "center",
                    }}
                  >
                    <ExternalLink size={16} />
                    Open Drive Folder
                  </a>
                </div>
                <p style={{ fontSize: 11, color: "var(--color-text-faint)", lineHeight: 1.5 }}>
                  Hand the iPad to the talent and have them open the folder link, then fill and sign all PDF forms. Return the iPad when complete.
                </p>
              </>
            ) : (
              <>
                <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 14, lineHeight: 1.4 }}>
                  Creates the Drive folder and copies PDF templates for today&apos;s shoot.
                  {selected.male_talent && !prepResult?.male_known && (
                    <> Male PDF dates will be pre-filled automatically for known talent.</>
                  )}
                </p>
                <button
                  onClick={prepareDocs}
                  disabled={preparing}
                  style={{
                    width: "100%",
                    background: preparing ? "var(--color-elevated)" : "var(--color-lime)",
                    border: "none", borderRadius: 10,
                    padding: "16px 20px",
                    fontSize: 15, fontWeight: 700, cursor: preparing ? "not-allowed" : "pointer",
                    color: preparing ? "var(--color-text-faint)" : "#000",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  }}
                >
                  {preparing ? <><Loader2 size={16} className="animate-spin" /> Preparing…</> : <><FileText size={16} /> Prepare Docs</>}
                </button>
                {prepError && (
                  <p style={{ fontSize: 12, color: "#f87171", marginTop: 8 }}>{prepError}</p>
                )}
              </>
            )}
          </div>

          {/* Talent info */}
          <div style={{
            background: "var(--color-surface)", border: "1px solid var(--color-border)",
            borderRadius: 12, padding: 14, marginBottom: 20,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>
              Talent
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Female</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)" }}>{selected.female_talent}</span>
              </div>
              {selected.male_talent && (
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Male</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)" }}>{selected.male_talent}</span>
                </div>
              )}
            </div>
          </div>

          {/* Navigation */}
          <button
            onClick={() => setStep("photos")}
            disabled={!prepResult}
            style={{
              width: "100%",
              background: prepResult ? accent : "var(--color-elevated)",
              border: "none", borderRadius: 10, padding: "16px 20px",
              fontSize: 15, fontWeight: 700,
              color: prepResult ? "#000" : "var(--color-text-faint)",
              cursor: prepResult ? "pointer" : "not-allowed",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            }}
          >
            Continue to Photos <ChevronRight size={16} />
          </button>
        </div>
      )}

      {/* ── Step: Photos ── */}
      {step === "photos" && selected && (
        <div style={{ padding: 16 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
            Step 2 — ID &amp; Verification Photos
          </h2>
          <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginBottom: 16, lineHeight: 1.4 }}>
            Capture both IDs side by side (front face, then back), then bunny ear shots for each talent.
          </p>

          {/* Female section */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: accent, marginBottom: 10 }}>
              {selected.female_talent}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {slots.filter(s => s.talent === "female").map(slot => {
                const captured = photos.find(p => p.slotId === slot.id)
                return (
                  <CameraButton
                    key={slot.id}
                    slot={slot}
                    captured={captured}
                    onCapture={(file, preview) => capturePhoto(slot, file, preview)}
                  />
                )
              })}
            </div>
          </div>

          {/* Male section */}
          {selected.male_talent && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-muted)", marginBottom: 10 }}>
                {selected.male_talent}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {slots.filter(s => s.talent === "male").map(slot => {
                  const captured = photos.find(p => p.slotId === slot.id)
                  return (
                    <CameraButton
                      key={slot.id}
                      slot={slot}
                      captured={captured}
                      onCapture={(file, preview) => capturePhoto(slot, file, preview)}
                    />
                  )
                })}
              </div>
            </div>
          )}

          {/* Required check */}
          {(() => {
            const required = slots.filter(s => s.required)
            const done = required.filter(s => photos.some(p => p.slotId === s.id))
            const allDone = done.length === required.length
            return (
              <div style={{
                background: "var(--color-surface)", border: "1px solid var(--color-border)",
                borderRadius: 10, padding: "12px 14px", marginBottom: 16,
                display: "flex", alignItems: "center", gap: 10,
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                  background: allDone ? "rgba(190,214,47,0.15)" : "rgba(255,255,255,0.04)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  {allDone
                    ? <CheckCircle2 size={18} color="var(--color-lime)" />
                    : <Camera size={18} color="var(--color-text-faint)" />
                  }
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)" }}>
                    {done.length} / {required.length} photos captured
                  </div>
                  {!allDone && (
                    <div style={{ fontSize: 11, color: "var(--color-text-faint)" }}>
                      {required.filter(s => !photos.some(p => p.slotId === s.id)).map(s => s.display).join(", ")} still needed
                    </div>
                  )}
                </div>
              </div>
            )
          })()}

          {/* Navigation */}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => setStep("docs")}
              style={{
                flex: 0, background: "transparent", border: "1px solid var(--color-border)",
                borderRadius: 10, padding: "14px 18px", cursor: "pointer",
                color: "var(--color-text-muted)", fontSize: 14,
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setStep("upload")}
              disabled={photos.length === 0}
              style={{
                flex: 1,
                background: photos.length > 0 ? accent : "var(--color-elevated)",
                border: "none", borderRadius: 10, padding: "16px 20px",
                fontSize: 15, fontWeight: 700,
                color: photos.length > 0 ? "#000" : "var(--color-text-faint)",
                cursor: photos.length > 0 ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              }}
            >
              Continue to Upload <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* ── Step: Upload ── */}
      {step === "upload" && selected && (
        <div style={{ padding: 16 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
            Step 3 — Upload &amp; File
          </h2>
          <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginBottom: 16, lineHeight: 1.4 }}>
            Upload all photos to the Drive legal folder, then copy the complete package to MEGA.
          </p>

          {/* Photo summary */}
          <div style={{
            background: "var(--color-surface)", border: "1px solid var(--color-border)",
            borderRadius: 12, padding: 14, marginBottom: 14,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-faint)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>
              Photos to Upload ({photos.length})
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
              {photos.map(p => (
                <div key={p.slotId} style={{ position: "relative", aspectRatio: "1", borderRadius: 8, overflow: "hidden" }}>
                  <img src={p.preview} alt={p.label} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  <button
                    onClick={() => removePhoto(p.slotId)}
                    style={{
                      position: "absolute", top: 3, right: 3,
                      background: "rgba(0,0,0,0.6)", border: "none", borderRadius: "50%",
                      width: 20, height: 20, cursor: "pointer", color: "#fff",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      padding: 0,
                    }}
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Upload result */}
          {uploadResult && (
            <div style={{
              background: uploadResult.errors.length > 0 ? "rgba(239,68,68,0.08)" : "rgba(190,214,47,0.08)",
              border: `1px solid ${uploadResult.errors.length > 0 ? "rgba(239,68,68,0.3)" : "rgba(190,214,47,0.3)"}`,
              borderRadius: 10, padding: "12px 14px", marginBottom: 14,
            }}>
              {uploadResult.uploaded.length > 0 && (
                <p style={{ fontSize: 12, color: "var(--color-lime)", marginBottom: 4 }}>
                  <CheckCircle2 size={12} style={{ display: "inline", marginRight: 4 }} />
                  {uploadResult.uploaded.length} file{uploadResult.uploaded.length !== 1 ? "s" : ""} uploaded to Drive
                </p>
              )}
              {uploadResult.errors.map((e, i) => (
                <p key={i} style={{ fontSize: 12, color: "#f87171" }}>{e}</p>
              ))}
            </div>
          )}

          {/* MEGA sync result */}
          {syncResult && (
            <div style={{
              background: syncResult.status === "ok" ? "rgba(190,214,47,0.08)" : "rgba(239,68,68,0.08)",
              border: `1px solid ${syncResult.status === "ok" ? "rgba(190,214,47,0.3)" : "rgba(239,68,68,0.3)"}`,
              borderRadius: 10, padding: "12px 14px", marginBottom: 14,
            }}>
              <p style={{ fontSize: 12, color: syncResult.status === "ok" ? "var(--color-lime)" : "#f87171" }}>
                {syncResult.message}
              </p>
            </div>
          )}

          {/* Drive folder link */}
          {prepResult?.folder_url && (
            <a
              href={prepResult.folder_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex", alignItems: "center", gap: 8,
                background: "var(--color-surface)", border: "1px solid var(--color-border)",
                borderRadius: 10, padding: "12px 16px", marginBottom: 14,
                color: "var(--color-text-muted)", fontSize: 13, textDecoration: "none",
              }}
            >
              <FolderOpen size={15} color={accent} />
              <span style={{ flex: 1 }}>View Drive Folder</span>
              <ExternalLink size={13} />
            </a>
          )}

          {/* Action buttons */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <button
              onClick={uploadAll}
              disabled={uploading || photos.length === 0}
              style={{
                width: "100%",
                background: uploading || photos.length === 0 ? "var(--color-elevated)" : "var(--color-lime)",
                border: "none", borderRadius: 10, padding: "16px 20px",
                fontSize: 15, fontWeight: 700,
                color: uploading || photos.length === 0 ? "var(--color-text-faint)" : "#000",
                cursor: uploading || photos.length === 0 ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              }}
            >
              {uploading
                ? <><Loader2 size={16} className="animate-spin" /> Uploading…</>
                : uploadResult?.uploaded.length
                  ? <><CheckCircle2 size={16} /> Re-Upload Photos</>
                  : <><Upload size={16} /> Upload to Drive</>
              }
            </button>

            {selected.scene_id && selected.studio && (
              <button
                onClick={syncMega}
                disabled={syncing || (!uploadResult?.uploaded.length && !selected.photos_uploaded)}
                style={{
                  width: "100%",
                  background: syncing ? "var(--color-elevated)" : "transparent",
                  border: `1px solid ${(!uploadResult?.uploaded.length && !selected.photos_uploaded) ? "var(--color-border)" : accent}`,
                  borderRadius: 10, padding: "16px 20px",
                  fontSize: 15, fontWeight: 700,
                  color: (!uploadResult?.uploaded.length && !selected.photos_uploaded) ? "var(--color-text-faint)" : accent,
                  cursor: (!uploadResult?.uploaded.length && !selected.photos_uploaded) || syncing ? "not-allowed" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}
              >
                {syncing
                  ? <><Loader2 size={16} className="animate-spin" /> Syncing to MEGA…</>
                  : syncResult?.status === "ok"
                    ? <><CheckCircle2 size={16} /> Synced to MEGA</>
                    : <>Copy to MEGA — {selected.scene_id}</>
                }
              </button>
            )}
          </div>

          {/* Back */}
          <button
            onClick={() => setStep("photos")}
            style={{
              marginTop: 14, background: "transparent", border: "none", cursor: "pointer",
              color: "var(--color-text-faint)", fontSize: 13,
              display: "flex", alignItems: "center", gap: 4,
            }}
          >
            <ChevronLeft size={14} /> Back to Photos
          </button>
        </div>
      )}
    </div>
  )
}
