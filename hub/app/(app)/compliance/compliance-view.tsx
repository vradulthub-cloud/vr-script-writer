"use client"

import { useEffect, useRef, useState } from "react"
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
  Video,
  X,
} from "lucide-react"
import { api, type ComplianceShoot, type CompliancePrepareResult, type FillFormRequest } from "@/lib/api"

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

const STUDIO_CODE: Record<string, string> = {
  FuckPassVR: "FPVR",
  VRHush:     "VRH",
  VRAllure:   "VRA",
  NaughtyJOI: "NJOI",
}

function studioCode(studio: string) {
  return STUDIO_CODE[studio] ?? studio.slice(0, 4).toUpperCase()
}

// Known male talent whose full form data is pre-stored in Drive templates.
// They only need dates auto-filled via the `prepare` endpoint.
const KNOWN_MALES = new Set(["MikeMancini", "JaydenMarcos", "DannySteele"])

// ─── Form data ────────────────────────────────────────────────────────────────

interface TalentFormData {
  legal_name: string
  stage_name: string
  dob: string
  place_of_birth: string
  street_address: string
  city_state_zip: string
  phone: string
  email: string
  id1_type: string
  id1_number: string
  id2_type: string
  id2_number: string
  signature: string
}

function emptyForm(): TalentFormData {
  return {
    legal_name: "", stage_name: "", dob: "", place_of_birth: "",
    street_address: "", city_state_zip: "", phone: "", email: "",
    id1_type: "", id1_number: "", id2_type: "", id2_number: "",
    signature: "",
  }
}

// ─── TalentForm component ─────────────────────────────────────────────────────

const ID_TYPES = [
  "US Passport",
  "Driver's License",
  "State ID Card",
  "Military ID",
  "Permanent Resident Card",
  "Foreign Passport",
] as const

// Returns the whole-years age at `asOf` (today by default). NaN if dob unparseable.
function computeAge(dobIso: string, asOf = new Date()): number {
  if (!dobIso) return NaN
  const d = new Date(dobIso + "T12:00:00")
  if (!Number.isFinite(d.getTime())) return NaN
  let age = asOf.getFullYear() - d.getFullYear()
  const m = asOf.getMonth() - d.getMonth()
  if (m < 0 || (m === 0 && asOf.getDate() < d.getDate())) age -= 1
  return age
}

function TalentForm({
  talentLabel,
  accent,
  submitting,
  error,
  onSubmit,
}: {
  talentLabel: string
  accent: string
  submitting: boolean
  error: string | null
  onSubmit: (data: TalentFormData) => void
}) {
  const [form, setForm] = useState<TalentFormData>(emptyForm)
  const [reviewing, setReviewing] = useState(false)
  const set = (k: keyof TalentFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const inputStyle: React.CSSProperties = {
    width: "100%",
    background: "var(--color-elevated)",
    border: "1px solid var(--color-border)",
    borderRadius: 8,
    padding: "13px 14px",
    fontSize: 16,
    color: "var(--color-text)",
    outline: "none",
    boxSizing: "border-box",
  }

  function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
      <div style={{ marginBottom: 18 }}>
        <div style={{
          fontSize: 13, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8,
        }}>
          {title}
        </div>
        <div style={{
          background: "var(--color-surface)", border: "1px solid var(--color-border)",
          borderRadius: 12, overflow: "hidden",
        }}>
          {children}
        </div>
      </div>
    )
  }

  function Field({
    label, fieldKey, type = "text", inputMode, placeholder, required,
  }: {
    label: string
    fieldKey: keyof TalentFormData
    type?: string
    inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"]
    placeholder?: string
    required?: boolean
  }) {
    return (
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--color-border-subtle)" }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
          {label}{required && <span style={{ color: accent, marginLeft: 3 }}>*</span>}
        </div>
        <input
          type={type}
          inputMode={inputMode}
          placeholder={placeholder}
          value={form[fieldKey]}
          onChange={set(fieldKey)}
          required={required}
          style={inputStyle}
        />
      </div>
    )
  }

  function SelectField({
    label, fieldKey, options, required,
  }: {
    label: string
    fieldKey: keyof TalentFormData
    options: readonly string[]
    required?: boolean
  }) {
    return (
      <div style={{ padding: "12px 14px", borderRight: "1px solid var(--color-border-subtle)", borderTop: "1px solid var(--color-border-subtle)" }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
          {label}{required && <span style={{ color: accent, marginLeft: 3 }}>*</span>}
        </div>
        <select
          value={form[fieldKey]}
          onChange={set(fieldKey)}
          style={{
            ...inputStyle,
            appearance: "none", WebkitAppearance: "none",
            backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>")`,
            backgroundRepeat: "no-repeat",
            backgroundPosition: "right 12px center",
            paddingRight: 34,
          }}
        >
          <option value="">Select…</option>
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    )
  }

  function TwoCol({ children }: { children: React.ReactNode }) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
        {children}
      </div>
    )
  }

  const age = computeAge(form.dob)
  const underage = Number.isFinite(age) && age < 18
  const isValid =
    form.legal_name.trim() !== "" &&
    form.signature.trim() !== "" &&
    !!form.dob &&
    !underage &&
    form.id1_type !== "" &&
    form.id1_number.trim() !== ""

  // ─── Confirm details preview ─────────────────────────────────────────
  if (reviewing) {
    return (
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
          Confirm your details
        </div>
        <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 16, lineHeight: 1.5 }}>
          This is what will appear on your signed paperwork. Check each line, then tap Generate to create the document.
        </p>

        <div style={{
          background: "var(--color-surface)", border: "1px solid var(--color-border)",
          borderRadius: 12, overflow: "hidden", marginBottom: 14,
        }}>
          <ReviewRow label="Legal name" value={form.legal_name} />
          <ReviewRow label="Stage name" value={form.stage_name || "—"} />
          <ReviewRow label="Date of birth" value={formatDob(form.dob)} />
          <ReviewRow label="Place of birth" value={form.place_of_birth || "—"} />
          <ReviewRow label="Address" value={[form.street_address, form.city_state_zip].filter(Boolean).join(", ") || "—"} />
          <ReviewRow label="Phone · Email" value={[form.phone, form.email].filter(Boolean).join(" · ") || "—"} />
          <ReviewRow label="Primary ID" value={form.id1_type && form.id1_number ? `${form.id1_type} · ${form.id1_number}` : "—"} />
          <ReviewRow label="Secondary ID" value={form.id2_type && form.id2_number ? `${form.id2_type} · ${form.id2_number}` : "—"} />
          <ReviewRow label="Signature" value={form.signature} italic last />
        </div>

        {error && (
          <div style={{
            background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 8, padding: "10px 14px", marginBottom: 14,
            fontSize: 13, color: "#f87171",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginBottom: 32 }}>
          <button
            onClick={() => setReviewing(false)}
            disabled={submitting}
            style={{
              flex: "0 0 auto",
              background: "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: 10, padding: "14px 18px",
              fontSize: 14, fontWeight: 600,
              color: "var(--color-text-muted)",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            Edit
          </button>
          <button
            onClick={() => !submitting && onSubmit(form)}
            disabled={submitting}
            style={{
              flex: 1,
              background: submitting ? "var(--color-elevated)" : "var(--color-lime)",
              border: "none", borderRadius: 10, padding: "16px 20px",
              fontSize: 15, fontWeight: 700,
              color: submitting ? "var(--color-text-faint)" : "#000",
              cursor: submitting ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            }}
          >
            {submitting
              ? <><Loader2 size={16} className="animate-spin" /> Generating…</>
              : <><FileText size={16} /> Generate PDF</>
            }
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
        {talentLabel}
      </div>

      {/* What you're signing — disclosure up top */}
      <div style={{
        background: "var(--color-elevated)",
        border: "1px solid var(--color-border)",
        borderRadius: 10, padding: "14px 16px", marginBottom: 18,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", marginBottom: 8 }}>
          What you&apos;re agreeing to
        </div>
        <ul style={{ margin: 0, padding: "0 0 0 16px", display: "flex", flexDirection: "column", gap: 4 }}>
          {[
            "Performer services agreement — confirms you are performing voluntarily",
            "18 U.S.C. § 2257 records — ID documentation required by federal law",
            "Model release — grants production rights to the content recorded today",
            "You may request a copy of the signed agreement at any time",
          ].map((line, i) => (
            <li key={i} style={{ fontSize: 12.5, color: "var(--color-text-muted)", lineHeight: 1.55 }}>{line}</li>
          ))}
        </ul>
        <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginTop: 10, marginBottom: 0, lineHeight: 1.5 }}>
          After submitting this form you&apos;ll review the full agreement before signing.
        </p>
      </div>

      <Section title="Identity">
        <Field label="Legal name (as shown on ID)" fieldKey="legal_name" placeholder="Full legal name" required />
        <Field label="Stage / performer name" fieldKey="stage_name" placeholder="Screen name" />
      </Section>

      <Section title="Personal info">
        <Field label="Date of birth" fieldKey="dob" type="date" required />
        {underage && (
          <div style={{
            padding: "8px 14px", borderBottom: "1px solid var(--color-border-subtle)",
            background: "rgba(239,68,68,0.08)",
            fontSize: 12, color: "#f87171", lineHeight: 1.5,
          }}>
            Talent must be 18 or older to sign. This date of birth is {age} — please double-check it.
          </div>
        )}
        <div style={{ padding: "12px 14px" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
            Place of birth
          </div>
          <input
            placeholder="City, State / Country"
            value={form.place_of_birth}
            onChange={set("place_of_birth")}
            style={inputStyle}
          />
        </div>
      </Section>

      <Section title="Address & contact">
        <Field label="Street address" fieldKey="street_address" placeholder="123 Main St, Apt 4" inputMode="text" />
        <Field label="City, State & ZIP" fieldKey="city_state_zip" placeholder="Los Angeles, CA 90210" inputMode="text" />
        <Field label="Phone" fieldKey="phone" type="tel" inputMode="tel" placeholder="(555) 000-0000" />
        <div style={{ padding: "12px 14px" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
            Email
          </div>
          <input
            type="email"
            inputMode="email"
            placeholder="email@example.com"
            value={form.email}
            onChange={set("email")}
            style={inputStyle}
          />
        </div>
      </Section>

      <Section title="ID documents">
        <TwoCol>
          <div style={{ padding: "12px 14px", borderRight: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              Primary ID type<span style={{ color: accent, marginLeft: 3 }}>*</span>
            </div>
            <select
              value={form.id1_type}
              onChange={set("id1_type")}
              style={{
                ...inputStyle,
                appearance: "none", WebkitAppearance: "none",
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 12px center",
                paddingRight: 34,
              }}
            >
              <option value="">Select…</option>
              {ID_TYPES.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div style={{ padding: "12px 14px" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              ID number<span style={{ color: accent, marginLeft: 3 }}>*</span>
            </div>
            <input placeholder="A12345678" value={form.id1_number} onChange={set("id1_number")} style={inputStyle} />
          </div>
        </TwoCol>
        <TwoCol>
          <SelectField label="Secondary ID type" fieldKey="id2_type" options={ID_TYPES} />
          <div style={{ padding: "12px 14px", borderTop: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              ID number
            </div>
            <input placeholder="D1234567" value={form.id2_number} onChange={set("id2_number")} style={inputStyle} />
          </div>
        </TwoCol>
      </Section>

      <Section title="Electronic signature">
        <div style={{ padding: "12px 14px" }}>
          <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", marginBottom: 10, lineHeight: 1.55 }}>
            Type your full legal name to confirm the information above is accurate. You&apos;ll read the full agreement on the next screen before it&apos;s final.
          </p>
          <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
            Full legal name (signature)<span style={{ color: accent, marginLeft: 3 }}>*</span>
          </div>
          <input
            placeholder="Type your full legal name"
            value={form.signature}
            onChange={set("signature")}
            style={{ ...inputStyle, fontStyle: "italic", fontSize: 18 }}
          />
        </div>
      </Section>

      {error && (
        <div style={{
          background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
          borderRadius: 8, padding: "10px 14px", marginBottom: 14,
          fontSize: 13, color: "#f87171",
        }}>
          {error}
        </div>
      )}

      <button
        onClick={() => isValid && setReviewing(true)}
        disabled={!isValid}
        style={{
          width: "100%",
          background: !isValid ? "var(--color-elevated)" : accent,
          border: "none", borderRadius: 10, padding: "16px 20px",
          fontSize: 15, fontWeight: 700,
          color: !isValid ? "var(--color-text-faint)" : "#000",
          cursor: !isValid ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          marginBottom: 32,
        }}
      >
        <FileText size={16} /> Review details
      </button>
    </div>
  )
}

function ReviewRow({
  label, value, italic, last,
}: {
  label: string
  value: string
  italic?: boolean
  last?: boolean
}) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "120px 1fr", gap: 12,
      padding: "10px 14px",
      borderBottom: last ? "none" : "1px solid var(--color-border-subtle)",
    }}>
      <div style={{ fontSize: 12, color: "var(--color-text-faint)" }}>{label}</div>
      <div style={{
        fontSize: italic ? 15 : 13,
        color: "var(--color-text)", wordBreak: "break-word",
        fontStyle: italic ? "italic" : "normal",
      }}>
        {value || "—"}
      </div>
    </div>
  )
}

function formatDob(iso: string): string {
  if (!iso) return "—"
  const d = new Date(iso + "T12:00:00")
  if (!Number.isFinite(d.getTime())) return iso
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })
}

// Resize a captured image to a max edge of `maxEdge` and re-encode as JPEG
// at the given quality. Phone JPEGs (5-10 MB at 12 MP) come back at ~300-800 KB
// at 2048 px / 0.82 quality — uploads complete in seconds instead of minutes.
async function compressImage(file: File, maxEdge: number, quality: number): Promise<File> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height))
  const w = Math.round(bitmap.width  * scale)
  const h = Math.round(bitmap.height * scale)
  const canvas = document.createElement("canvas")
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext("2d")
  if (!ctx) throw new Error("canvas 2d context unavailable")
  ctx.drawImage(bitmap, 0, 0, w, h)
  bitmap.close()
  const blob: Blob = await new Promise((resolve, reject) =>
    canvas.toBlob(b => b ? resolve(b) : reject(new Error("toBlob failed")), "image/jpeg", quality)
  )
  // Preserve original filename but force .jpg extension
  const baseName = file.name.replace(/\.(heic|heif|png|webp|jpe?g)$/i, "")
  return new File([blob], `${baseName}.jpg`, { type: "image/jpeg", lastModified: Date.now() })
}

// ─── ReviewCard component ─────────────────────────────────────────────────────

function ReviewCard({
  display,
  shootId,
  talent,
  studio,
  accent,
  onSkip,
}: {
  display: string
  shootId: string
  talent: string
  studio: string
  accent: string
  onSkip: () => void
}) {
  function openSignTab() {
    const url = `/sign/${encodeURIComponent(shootId)}?talent=${encodeURIComponent(talent)}&display=${encodeURIComponent(display)}&studio=${encodeURIComponent(studio)}`
    window.open(url, "_blank", "noopener")
  }

  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
        {display} — Read &amp; Sign
      </div>
      <p style={{ fontSize: 13, color: "var(--color-text-faint)", marginBottom: 12, lineHeight: 1.5 }}>
        Your paperwork has been prepared. Tap the button below to read the full agreement — you must read it before signing.
      </p>
      <div style={{
        background: "rgba(255,255,255,0.04)", border: "1px solid var(--color-border)",
        borderRadius: 8, padding: "10px 14px", marginBottom: 20,
        fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.6,
      }}>
        The document contains your performer services agreement, 2257 records disclosure, and model release.
        Read it carefully — your electronic signature confirms you understood and agreed to its terms.
      </div>

      <button
        onClick={openSignTab}
        style={{
          width: "100%",
          background: accent,
          border: "none", borderRadius: 12, padding: "18px 20px",
          fontSize: 16, fontWeight: 700, color: "#000",
          cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          marginBottom: 14,
        }}
      >
        <FileText size={18} />
        Read &amp; Sign Agreement — {display}
      </button>

      <p style={{ fontSize: 11, color: "var(--color-text-faint)", textAlign: "center", lineHeight: 1.5, marginBottom: 8 }}>
        Opens in a new tab. This page will advance automatically when they confirm.
      </p>

      <button
        onClick={() => {
          if (window.confirm(
            "Confirm: talent has already signed this agreement on paper.\n\n" +
            "This will skip the digital signature step. Only use this when a physical signed copy has been collected."
          )) onSkip()
        }}
        style={{
          width: "100%", background: "transparent",
          border: "1px solid var(--color-border-subtle)", cursor: "pointer",
          color: "var(--color-text-faint)", fontSize: 12,
          padding: "10px 12px", borderRadius: 8,
        }}
      >
        Already signed on paper — skip digital signature
      </button>
    </div>
  )
}

// ─── Photo slot definition ────────────────────────────────────────────────────

interface PhotoSlot {
  id: string
  label: string  // used as filename
  display: string
  talent: "female" | "male"
  category: "id" | "bunny" | "signout"
  required: boolean
  fileType?: "image" | "video"
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
  slots.push({
    id: "signout-video",
    label: "signout-video.mp4",
    display: "Sign Out Video",
    talent: "female",
    category: "signout",
    required: true,
    fileType: "video",
  })
  return slots
}

// ─── Captured photo state ─────────────────────────────────────────────────────

interface CapturedPhoto {
  slotId: string
  label: string
  file: File
  preview: string
  fileType?: "image" | "video"
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
        background: "rgba(255,255,255,0.06)", color: "var(--color-text-muted)",
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
  const isVideo = slot.fileType === "video"

  async function handleFile(file: File) {
    // For images, compress to max 2048px / ~80% JPEG to keep upload sizes
    // sane (phone JPEGs are 5-10MB; this gets us to ~300-800KB).
    // Videos pass through unchanged.
    let outFile = file
    if (!isVideo && file.type.startsWith("image/")) {
      try {
        outFile = await compressImage(file, 2048, 0.82)
      } catch {
        // fall back to original on any failure
        outFile = file
      }
    }
    const url = URL.createObjectURL(outFile)
    onCapture(outFile, url)
  }

  return (
    <div style={{ position: "relative" }}>
      {/* Hidden inputs */}
      <input
        ref={inputRef}
        type="file"
        accept={isVideo ? "video/*" : "image/*"}
        capture="environment"
        style={{ display: "none" }}
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = "" }}
      />
      <input
        ref={uploadRef}
        type="file"
        accept={isVideo ? "video/*" : "image/*"}
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
          aspectRatio: isVideo ? "16/9" : "4/3",
          cursor: "pointer",
        }}
        onClick={() => inputRef.current?.click()}
      >
        {captured ? (
          /* Preview */
          <>
            {isVideo ? (
              <video
                src={captured.preview}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                playsInline
                muted
              />
            ) : (
              <img
                src={captured.preview}
                alt={slot.display}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            )}
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
                <RefreshCw size={11} /> {isVideo ? "Re-record" : "Retake"}
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
              {isVideo
                ? <Video size={22} color="var(--color-text-muted)" />
                : <Camera size={22} color="var(--color-text-muted)" />
              }
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
                {isVideo ? <><Video size={12} /> Record</> : <><Camera size={12} /> Camera</>}
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
type DocsPhase = "female" | "female-review" | "male-known" | "male-form" | "male-review" | "done"

export function ComplianceView({ initialShoots, initialDate, idToken, loadError }: Props) {
  const client = api(idToken ?? null)

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
  // Which sub-step within docs: female form → male (known/unknown/none) → done
  const [docsPhase, setDocsPhase] = useState<DocsPhase>("female")
  const [femaleSubmitting, setFemaleSubmitting] = useState(false)
  const [femaleError, setFemaleError] = useState<string | null>(null)
  const [maleSubmitting, setMaleSubmitting] = useState(false)
  const [maleError, setMaleError] = useState<string | null>(null)

  // Photos step state
  const [photos, setPhotos] = useState<CapturedPhoto[]>([])

  // Upload step state
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null)
  const [uploadResult, setUploadResult] = useState<{ uploaded: string[]; errors: string[]; mega_paths: string[] } | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ status: string; message: string } | null>(null)

  const slots = selected ? buildSlots(selected.female_talent, selected.male_talent) : []

  // ── Listen for sign-tab confirmations ─────────────────────────────────
  // The /sign/[shootId] page posts "compliance:signed:{talentSlug}" when
  // the talent taps "I Agree", allowing this tab to auto-advance.
  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.origin !== window.location.origin) return
      const data = String(e.data)
      if (!data.startsWith("compliance:signed:")) return
      const signedTalent = data.replace("compliance:signed:", "")
      setDocsPhase(prev => {
        if (prev === "female-review") {
          if (!selected?.male_talent) return "done"
          return KNOWN_MALES.has(selected.male_talent) ? "male-known" : "male-form"
        }
        if (prev === "male-review") return "done"
        return prev
      })
      void loadDate(date)
    }
    window.addEventListener("message", onMessage)
    return () => window.removeEventListener("message", onMessage)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, date])

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
    // If both talent already have signed PDFs, skip the form flow and go
    // straight to the "done" view so the user can view existing documents.
    setDocsPhase(shoot.pdfs_ready ? "done" : "female")
    setFemaleSubmitting(false)
    setFemaleError(null)
    setMaleSubmitting(false)
    setMaleError(null)
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
        message: shoot.pdfs_ready ? "Signed documents already on file" : "Folder already exists",
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

  // ── Form submit handlers ──────────────────────────────────────────────

  async function submitFemaleForm(data: TalentFormData) {
    if (!selected) return
    setFemaleSubmitting(true)
    setFemaleError(null)
    try {
      const req: FillFormRequest = { talent: "female", ...data }
      const r = await client.compliance.fillForm(selected.shoot_id, req)
      setPrepResult(r)
      void loadDate(date)
      setDocsPhase("female-review")
    } catch (e) {
      setFemaleError(e instanceof Error ? e.message : "Failed to save form")
    } finally {
      setFemaleSubmitting(false)
    }
  }

  async function submitMaleKnown() {
    if (!selected) return
    setMaleSubmitting(true)
    setMaleError(null)
    try {
      const r = await client.compliance.prepare(selected.shoot_id)
      setPrepResult(r)
      void loadDate(date)
      setDocsPhase("male-review")
    } catch (e) {
      setMaleError(e instanceof Error ? e.message : "Failed to generate male form")
    } finally {
      setMaleSubmitting(false)
    }
  }

  async function submitMaleForm(data: TalentFormData) {
    if (!selected) return
    setMaleSubmitting(true)
    setMaleError(null)
    try {
      const req: FillFormRequest = { talent: selected.male_talent, ...data }
      const r = await client.compliance.fillForm(selected.shoot_id, req)
      setPrepResult(r)
      void loadDate(date)
      setDocsPhase("male-review")
    } catch (e) {
      setMaleError(e instanceof Error ? e.message : "Failed to save form")
    } finally {
      setMaleSubmitting(false)
    }
  }

  // ── Photo capture ─────────────────────────────────────────────────────

  function capturePhoto(slot: PhotoSlot, file: File, preview: string) {
    setPhotos(prev => {
      const without = prev.filter(p => p.slotId !== slot.id)
      return [...without, { slotId: slot.id, label: slot.label, file, preview, fileType: slot.fileType }]
    })
  }

  function removePhoto(slotId: string) {
    setPhotos(prev => prev.filter(p => p.slotId !== slotId))
  }

  // ── Upload ────────────────────────────────────────────────────────────

  async function uploadAll() {
    if (!selected || photos.length === 0) return
    setUploading(true)
    setUploadProgress({ done: 0, total: photos.length })
    setUploadResult(null)

    const uploaded: string[] = []
    const errors: string[] = []
    let mega_paths: string[] = []

    // Upload one file at a time so the user sees progress and individual failures
    // don't abort the whole batch.
    for (let i = 0; i < photos.length; i++) {
      setUploadProgress({ done: i, total: photos.length })
      const photo = photos[i]
      try {
        // 90s abort per file — generous for a compressed ~500 KB photo over Tailscale
        const abort = new AbortController()
        const timer = setTimeout(() => abort.abort(), 90_000)
        const r = await client.compliance.uploadPhotos(
          selected.shoot_id,
          [{ file: photo.file, label: photo.label }],
          selected.scene_id || undefined,
          selected.studio || undefined,
          abort.signal,
        )
        clearTimeout(timer)
        uploaded.push(...r.uploaded)
        if (r.mega_paths?.length) mega_paths = [...mega_paths, ...r.mega_paths]
        if (r.errors?.length) errors.push(...r.errors)
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Upload failed"
        errors.push(`${photo.label}: ${msg}`)
      }
    }

    setUploadProgress({ done: photos.length, total: photos.length })
    setUploadResult({ uploaded, errors, mega_paths })
    void loadDate(date)
    setUploading(false)
    setUploadProgress(null)
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
    <div style={{
      minHeight: "100vh", background: "var(--color-bg)",
      padding: "0 0 80px",
      maxWidth: 720, margin: "0 auto",
    }}>

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

          {/* Date navigation */}
          {(() => {
            const isToday = date === new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date())
            const label = new Date(date + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })
            function shiftDay(delta: number) {
              const d = new Date(date + "T12:00:00")
              d.setDate(d.getDate() + delta)
              const next = d.toISOString().slice(0, 10)
              handleDateChange(next)
            }
            return (
              <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 0 }}>
                <button
                  onClick={() => shiftDay(-1)}
                  aria-label="Previous day"
                  style={{
                    background: "var(--color-elevated)", border: "1px solid var(--color-border)",
                    borderRight: "none", borderRadius: "8px 0 0 8px",
                    color: "var(--color-text)", cursor: "pointer",
                    padding: "10px 14px", lineHeight: 1, display: "flex", alignItems: "center",
                  }}
                >
                  <ChevronLeft size={16} />
                </button>
                <div style={{
                  flex: 1, background: "var(--color-elevated)", border: "1px solid var(--color-border)",
                  padding: "10px 12px", textAlign: "center",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>{label}</span>
                  {isToday && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                      textTransform: "uppercase", color: "#bed62f",
                      background: "rgba(190,214,47,0.12)", borderRadius: 4,
                      padding: "2px 6px",
                    }}>Today</span>
                  )}
                  {!isToday && (
                    <button
                      onClick={() => handleDateChange(new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date()))}
                      style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                        textTransform: "uppercase", color: "var(--color-text-faint)",
                        background: "var(--color-surface)", border: "1px solid var(--color-border)",
                        borderRadius: 4, padding: "2px 6px", cursor: "pointer",
                      }}
                    >
                      Today
                    </button>
                  )}
                </div>
                <button
                  onClick={() => shiftDay(1)}
                  aria-label="Next day"
                  style={{
                    background: "var(--color-elevated)", border: "1px solid var(--color-border)",
                    borderLeft: "none", borderRadius: "0 8px 8px 0",
                    color: "var(--color-text)", cursor: "pointer",
                    padding: "10px 14px", lineHeight: 1, display: "flex", alignItems: "center",
                  }}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            )
          })()}

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
                      borderRadius: 12,
                      padding: "16px 18px",
                      cursor: "pointer",
                      textAlign: "left",
                      width: "100%",
                      display: "flex", alignItems: "center", gap: 14,
                    }}
                  >
                    <div
                      aria-hidden="true"
                      style={{
                        width: 40, height: 40, borderRadius: 10,
                        background: `color-mix(in oklab, ${sc} 18%, transparent)`,
                        color: sc,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 11, fontWeight: 700, letterSpacing: "0.04em",
                        flexShrink: 0,
                      }}
                    >
                      {studioCode(shoot.studio)}
                    </div>
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

          {/* Progress pills */}
          <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
            {[
              { phase: "female" as DocsPhase, label: selected.female_talent },
              ...(selected.male_talent ? [{ phase: (KNOWN_MALES.has(selected.male_talent) ? "male-known" : "male-form") as DocsPhase, label: selected.male_talent }] : []),
            ].map(({ phase, label }) => {
              const phases: DocsPhase[] = ["female", "female-review", "male-known", "male-form", "male-review", "done"]
              const currentIdx = phases.indexOf(docsPhase)
              // Consider "female-review" as the female step being active/done
              const relatedPhases: DocsPhase[] = phase === "female"
                ? ["female", "female-review"]
                : ["male-known", "male-form", "male-review"]
              const thisIdx = phases.indexOf(relatedPhases[0])
              const isDone = docsPhase === "done" || currentIdx > thisIdx + 1
              const isActive = relatedPhases.includes(docsPhase)
              return (
                <div key={phase} style={{
                  flex: 1, padding: "6px 10px", borderRadius: 8, fontSize: 11, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                  background: isDone ? "rgba(190,214,47,0.12)" : isActive ? "rgba(255,255,255,0.06)" : "transparent",
                  border: `1px solid ${isDone ? "rgba(190,214,47,0.3)" : isActive ? "var(--color-border)" : "var(--color-border-subtle)"}`,
                  color: isDone ? "var(--color-lime)" : isActive ? "var(--color-text)" : "var(--color-text-faint)",
                }}>
                  {isDone ? <CheckCircle2 size={12} /> : <span style={{ width: 12, height: 12, borderRadius: "50%", border: `2px solid ${isActive ? accent : "var(--color-border)"}`, display: "inline-block", flexShrink: 0 }} />}
                  {label}
                </div>
              )
            })}
          </div>

          {/* Phase: female review — open signed PDF in new tab */}
          {docsPhase === "female-review" && selected && (
            <ReviewCard
              display={selected.female_talent}
              shootId={selected.shoot_id}
              talent={selected.female_talent.replace(/ /g, "")}
              studio={selected.studio}
              accent={accent}
              onSkip={() => {
                if (!selected.male_talent) { setDocsPhase("done"); return }
                setDocsPhase(KNOWN_MALES.has(selected.male_talent) ? "male-known" : "male-form")
              }}
            />
          )}

          {/* Phase: female form */}
          {docsPhase === "female" && (
            <TalentForm
              talentLabel={`${selected.female_talent} — Female Talent Form`}
              accent={accent}
              submitting={femaleSubmitting}
              error={femaleError}
              onSubmit={submitFemaleForm}
            />
          )}

          {/* Phase: known male — auto-generate with date */}
          {docsPhase === "male-known" && selected.male_talent && (
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
                {selected.male_talent} — On File
              </div>
              <p style={{ fontSize: 13, color: "var(--color-text-faint)", marginBottom: 20, lineHeight: 1.5 }}>
                {selected.male_talent}&apos;s paperwork is pre-filled on file. Tap below to generate the form with today&apos;s shoot date.
              </p>
              {maleError && (
                <div style={{
                  background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
                  borderRadius: 8, padding: "10px 14px", marginBottom: 14,
                  fontSize: 13, color: "#f87171",
                }}>
                  {maleError}
                </div>
              )}
              <button
                onClick={submitMaleKnown}
                disabled={maleSubmitting}
                style={{
                  width: "100%",
                  background: maleSubmitting ? "var(--color-elevated)" : "var(--color-lime)",
                  border: "none", borderRadius: 10, padding: "16px 20px",
                  fontSize: 15, fontWeight: 700,
                  color: maleSubmitting ? "var(--color-text-faint)" : "#000",
                  cursor: maleSubmitting ? "not-allowed" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  marginBottom: 32,
                }}
              >
                {maleSubmitting
                  ? <><Loader2 size={16} className="animate-spin" /> Generating…</>
                  : <><FileText size={16} /> Generate Form</>
                }
              </button>
            </div>
          )}

          {/* Phase: unknown male form */}
          {docsPhase === "male-form" && selected.male_talent && (
            <TalentForm
              talentLabel={`${selected.male_talent} — Male Talent Form`}
              accent={accent}
              submitting={maleSubmitting}
              error={maleError}
              onSubmit={submitMaleForm}
            />
          )}

          {/* Phase: male review */}
          {docsPhase === "male-review" && selected?.male_talent && (
            <ReviewCard
              display={selected.male_talent}
              shootId={selected.shoot_id}
              talent={selected.male_talent.replace(/ /g, "")}
              studio={selected.studio}
              accent={accent}
              onSkip={() => setDocsPhase("done")}
            />
          )}

          {/* Phase: done — all forms complete */}
          {docsPhase === "done" && (
            <div>
              <div style={{
                background: "rgba(190,214,47,0.08)", border: "1px solid rgba(190,214,47,0.25)",
                borderRadius: 12, padding: "18px 20px", marginBottom: 20,
                display: "flex", alignItems: "center", gap: 14,
              }}>
                <CheckCircle2 size={24} color="var(--color-lime)" />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-lime)" }}>All forms complete</div>
                  {prepResult?.message && (
                    <div style={{ fontSize: 12, color: "var(--color-text-faint)", marginTop: 2 }}>{prepResult.message}</div>
                  )}
                </div>
              </div>

              {/* Signed documents on file — view existing PDFs */}
              {selected.pdfs_ready && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{
                    fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase",
                    color: "var(--color-text-faint)", marginBottom: 10,
                  }}>
                    Signed documents on file
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {[
                      { display: selected.female_talent, slug: selected.female_talent.replace(/ /g, "") },
                      ...(selected.male_talent
                        ? [{ display: selected.male_talent, slug: selected.male_talent.replace(/ /g, "") }]
                        : []),
                    ].map(({ display, slug }) => (
                      <a
                        key={slug}
                        href={`/api/compliance/${encodeURIComponent(selected.shoot_id)}/pdf?talent=${encodeURIComponent(slug)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          background: "var(--color-surface)", border: "1px solid var(--color-border)",
                          borderRadius: 10, padding: "12px 14px",
                          color: "var(--color-text)", fontSize: 14, fontWeight: 600,
                          textDecoration: "none",
                        }}
                      >
                        <FileText size={16} color={accent} />
                        <span style={{ flex: 1 }}>{display}</span>
                        <span style={{ fontSize: 11, color: "var(--color-text-faint)", fontWeight: 500 }}>
                          View signed PDF
                        </span>
                        <ExternalLink size={13} color="var(--color-text-faint)" />
                      </a>
                    ))}
                  </div>
                  {prepResult?.folder_url && (
                    <a
                      href={prepResult.folder_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 6,
                        marginTop: 10, fontSize: 12, color: "var(--color-text-faint)",
                        textDecoration: "none",
                      }}
                    >
                      <FolderOpen size={12} /> Open Drive folder
                    </a>
                  )}
                </div>
              )}

              <button
                onClick={() => setStep("photos")}
                style={{
                  width: "100%",
                  background: accent,
                  border: "none", borderRadius: 10, padding: "16px 20px",
                  fontSize: 15, fontWeight: 700, color: "#000",
                  cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}
              >
                Continue to Photos <ChevronRight size={16} />
              </button>
            </div>
          )}

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

          {/* Sign Out Video */}
          {(() => {
            const videoSlot = slots.find(s => s.category === "signout")
            if (!videoSlot) return null
            const captured = photos.find(p => p.slotId === videoSlot.id)
            return (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 6 }}>
                  Sign Out Video
                </div>
                <p style={{ fontSize: 11, color: "var(--color-text-faint)", marginBottom: 10, lineHeight: 1.4 }}>
                  Record talent confirming they participated willingly and were treated respectfully.
                </p>
                <CameraButton
                  slot={videoSlot}
                  captured={captured}
                  onCapture={(file, preview) => capturePhoto(videoSlot, file, preview)}
                />
              </div>
            )
          })()}

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
                  {p.fileType === "video" ? (
                    <div style={{
                      width: "100%", height: "100%",
                      background: "var(--color-elevated)",
                      display: "flex", flexDirection: "column",
                      alignItems: "center", justifyContent: "center", gap: 4,
                    }}>
                      <Video size={18} color="var(--color-lime)" />
                      <span style={{ fontSize: 9, color: "var(--color-text-faint)", textAlign: "center", padding: "0 4px" }}>
                        {p.label}
                      </span>
                    </div>
                  ) : (
                    <img src={p.preview} alt={p.label} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  )}
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
                ? <><Loader2 size={16} className="animate-spin" />
                    {uploadProgress
                      ? `Uploading ${uploadProgress.done + 1} / ${uploadProgress.total}…`
                      : "Uploading…"}
                  </>
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
