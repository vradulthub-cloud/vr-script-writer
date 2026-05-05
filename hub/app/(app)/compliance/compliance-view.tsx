"use client"

import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react"
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
import { api, ApiError, type CompliancePhoto, type ComplianceShoot, type CompliancePrepareResult, type DriveImportResult, type SignedSummary } from "@/lib/api"
import {
  AGREEMENT_SECTIONS,
  CONTRACT_INTRO,
  CONTRACT_TITLE,
  DATA_CONSENT,
  DISCLOSURE_HEADING,
  DISCLOSURE_STATEMENT,
  DOCUMENTS_PROVIDED_HEADING,
  DOCUMENTS_PROVIDED_LIST,
  EXECUTION_LINE,
  INDEMNITY_STATEMENT,
  PERJURY_STATEMENT,
  PRODUCER_NAME,
  WITNESS_STATEMENT,
} from "@/lib/compliance-contract"
import { SignaturePad } from "@/components/ui/signature-pad"
import { Letterhead, LockBanner } from "./paper-primitives"
import { SignatureEditModal } from "./signature-edit-modal"

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
  // W-9 fields (TKT-0150)
  business_name: string
  tax_classification: "individual" | "c_corp" | "s_corp" | "partnership" | "trust_estate" | "llc" | "other"
  llc_class: string                  // 'C' | 'S' | 'P' (only when tax_classification='llc')
  other_classification: string
  exempt_payee_code: string
  fatca_code: string
  tin_type: "ssn" | "ein"
  tin: string                        // raw digits, no formatting
}

function emptyForm(): TalentFormData {
  return {
    legal_name: "", stage_name: "", dob: "", place_of_birth: "",
    street_address: "", city_state_zip: "", phone: "", email: "",
    id1_type: "", id1_number: "", id2_type: "", id2_number: "",
    business_name: "", tax_classification: "individual",
    llc_class: "", other_classification: "",
    exempt_payee_code: "", fatca_code: "",
    tin_type: "ssn", tin: "",
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

// "123456789" → "123-45-6789" (SSN-style hyphenation for display).
function formatSsn(raw: string): string {
  const d = (raw || "").replace(/\D/g, "")
  if (d.length <= 3) return d
  if (d.length <= 5) return `${d.slice(0, 3)}-${d.slice(3)}`
  return `${d.slice(0, 3)}-${d.slice(3, 5)}-${d.slice(5)}`
}

// "123456789" → "12-3456789" (EIN format).
function formatEin(raw: string): string {
  const d = (raw || "").replace(/\D/g, "")
  if (d.length <= 2) return d
  return `${d.slice(0, 2)}-${d.slice(2)}`
}

function taxClassLabel(form: TalentFormData): string {
  switch (form.tax_classification) {
    case "individual":   return "Individual / Sole proprietor"
    case "c_corp":        return "C Corporation"
    case "s_corp":        return "S Corporation"
    case "partnership":   return "Partnership"
    case "trust_estate":  return "Trust / Estate"
    case "llc":           return `LLC (${form.llc_class || "?"})`
    case "other":         return `Other — ${form.other_classification || "?"}`
    default:              return form.tax_classification
  }
}

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

// ─── Form helper components (hoisted) ────────────────────────────────────
// These MUST live at module scope. Defining them inside TalentForm makes their
// function identity change on every render, which causes React to unmount and
// remount the inputs on every keystroke — losing focus after one character.

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

type FormCtxValue = {
  form: TalentFormData
  set: (k: keyof TalentFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void
  accent: string
}
const FormCtx = createContext<FormCtxValue | null>(null)
function useFormCtx(): FormCtxValue {
  const v = useContext(FormCtx)
  if (!v) throw new Error("FormCtx is missing — Field/SelectField must be inside <FormCtx.Provider>")
  return v
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

function TwoCol({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
      {children}
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
  const { form, set, accent } = useFormCtx()
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
  const { form, set, accent } = useFormCtx()
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

function TalentForm({
  talentLabel,
  accent,
  submitting,
  error,
  onSubmit,
  onBack,
  draftKey,
  prefillSource,
}: {
  talentLabel: string
  accent: string
  submitting: boolean
  error: string | null
  onSubmit: (data: TalentFormData) => void
  onBack?: () => void
  /**
   * Stable per-form key (e.g. `compliance-draft-${shoot_id}-female`). When set,
   * the form auto-saves to localStorage on every change and restores on mount.
   * Prevents the "API error nuked everything she just typed" failure mode.
   * Parent should clear localStorage[draftKey] after a successful sign.
   */
  draftKey?: string
  /**
   * When provided, the form fetches the talent's most recent paperwork
   * (within `withinDays`, default 365) on mount and seeds any fields that
   * are still empty. Skipped if a localStorage draft exists for `draftKey`
   * — we don't want prefill to clobber a partial typing session.
   */
  prefillSource?: {
    talentSlug: string
    role: "female" | "male"
    idToken?: string
    withinDays?: number
  }
}) {
  // Lazy init reads localStorage once on first render to seed form state.
  // SSR-safe: window check, JSON.parse guarded, falls back to empty form.
  // Also tracks whether a draft was found so we know to skip prefill.
  const [hadDraft] = useState(() => {
    if (typeof window === "undefined" || !draftKey) return false
    try {
      const raw = window.localStorage.getItem(draftKey)
      return !!raw
    } catch {
      return false
    }
  })
  const [form, setForm] = useState<TalentFormData>(() => {
    if (typeof window === "undefined" || !draftKey) return emptyForm()
    try {
      const raw = window.localStorage.getItem(draftKey)
      if (!raw) return emptyForm()
      const parsed = JSON.parse(raw) as Partial<TalentFormData>
      return { ...emptyForm(), ...parsed }
    } catch {
      return emptyForm()
    }
  })
  const [reviewing, setReviewing] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  // Prefill banner state — surfaces "Pre-filled from your last shoot"
  // so the talent (and the operator) know to review before submit.
  const [prefilledFrom, setPrefilledFrom] = useState<{
    signed_at: string
  } | null>(null)

  // Prefill effect: runs once on mount if no localStorage draft and we have
  // a prefill source. Seeds only fields that are currently empty so any
  // partial typing the talent did before the effect resolves wins.
  useEffect(() => {
    if (!prefillSource || hadDraft) return
    let cancelled = false
    const client = api(prefillSource.idToken ?? null)
    client.compliance
      .talentPrefill(prefillSource.talentSlug, prefillSource.role, prefillSource.withinDays ?? 365)
      .then((p) => {
        if (cancelled || !p?.found) return
        setForm((prev) => {
          const next = { ...prev }
          // Map server fields → form fields. Only fill currently-empty
          // ones so anything the talent already typed wins. Form keys
          // mirror TalentFormData exactly; the W-9 prefill mapping below
          // mirrors the field-name mismatches between server and form.
          const map: Array<[keyof TalentFormData, keyof typeof p]> = [
            ["legal_name",          "legal_name"],
            ["business_name",       "business_name"],
            ["dob",                 "dob"],
            ["place_of_birth",      "place_of_birth"],
            ["street_address",      "street_address"],
            ["city_state_zip",      "city_state_zip"],
            ["phone",               "phone"],
            ["email",               "email"],
            ["id1_type",            "id1_type"],
            ["id1_number",          "id1_number"],
            ["id2_type",            "id2_type"],
            ["id2_number",          "id2_number"],
            ["stage_name",          "stage_names"],
            ["llc_class",           "llc_class"],
            ["other_classification","other_classification"],
            ["exempt_payee_code",   "exempt_payee_code"],
            ["fatca_code",          "fatca_code"],
            ["tin",                 "tin"],
          ]
          for (const [formKey, prefillKey] of map) {
            if (!next[formKey] && p[prefillKey]) {
              ;(next as Record<string, unknown>)[formKey] = String(p[prefillKey] ?? "")
            }
          }
          // tax_classification + tin_type are typed unions — only override
          // when the prior value matches a known enum.
          if (p.tax_classification && next.tax_classification === "individual") {
            const v = p.tax_classification as TalentFormData["tax_classification"]
            if (
              v === "individual" || v === "c_corp" || v === "s_corp" ||
              v === "partnership" || v === "trust_estate" || v === "llc" ||
              v === "other"
            ) {
              next.tax_classification = v
            }
          }
          if (p.tin_type && (p.tin_type === "ssn" || p.tin_type === "ein")) {
            next.tin_type = p.tin_type
          }
          return next
        })
        setPrefilledFrom({ signed_at: p.source_signed_at ?? "" })
      })
      .catch(() => { /* prefill is best-effort */ })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const set = (k: keyof TalentFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  // Persist form state on every change. Cheap (<5KB) so we don't debounce.
  useEffect(() => {
    if (typeof window === "undefined" || !draftKey) return
    try {
      window.localStorage.setItem(draftKey, JSON.stringify(form))
    } catch {
      // Quota exceeded or storage disabled (private mode) — drop silently.
    }
  }, [draftKey, form])

  const formCtx = useMemo<FormCtxValue>(() => ({ form, set, accent }), [form, accent])

  const age = computeAge(form.dob)
  const underage = Number.isFinite(age) && age < 18
  // Real signature is captured on the next screen — the form just needs the
  // factual data filled in.
  const tinDigits = form.tin.replace(/\D/g, "")
  const tinExpectedLen = form.tin_type === "ssn" ? 9 : 9  // EIN is also 9
  const isValid =
    form.legal_name.trim() !== "" &&
    !!form.dob &&
    !underage &&
    form.id1_type !== "" &&
    form.id1_number.trim() !== "" &&
    tinDigits.length === tinExpectedLen &&
    form.street_address.trim() !== "" &&
    form.city_state_zip.trim() !== ""

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
          <ReviewRow label="Tax classification" value={taxClassLabel(form)} />
          <ReviewRow label="Business name" value={form.business_name || "—"} />
          <ReviewRow
            label={form.tin_type === "ssn" ? "SSN" : "EIN"}
            value={form.tin_type === "ssn" ? formatSsn(form.tin) : formatEin(form.tin)}
            last
          />
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
              ? <><Loader2 size={16} className="animate-spin" /> Loading…</>
              : <><FileText size={16} /> Hand iPad to talent →</>
            }
          </button>
        </div>
      </div>
    )
  }

  return (
    <FormCtx.Provider value={formCtx}>
    <div>
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            background: "transparent", border: "none",
            color: "var(--color-text-muted)", fontSize: 12, fontWeight: 600,
            padding: "0 0 8px", cursor: "pointer",
          }}
        >
          ← Back
        </button>
      )}
      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
        {talentLabel}
      </div>

      {/* Returning-talent prefill banner — surfaces the source shoot date so
          the talent (and operator) know to review every field before signing
          rather than blindly accepting prior info. Hidden when nothing was
          prefilled (new talent or window expired). */}
      {prefilledFrom && (
        <div style={{
          marginBottom: 14,
          padding: "10px 12px",
          background: "color-mix(in srgb, var(--color-lime) 8%, transparent)",
          border: "1px solid color-mix(in srgb, var(--color-lime) 28%, transparent)",
          borderRadius: 8,
          fontSize: 12, color: "var(--color-text)",
        }}>
          <strong style={{ color: "var(--color-lime)" }}>Pre-filled</strong>
          {" "}from your last paperwork
          {prefilledFrom.signed_at && (
            <> on {new Date(prefilledFrom.signed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</>
          )}
          .{" "}
          <span style={{ color: "var(--color-text-muted)" }}>
            Please review every field — anything that has changed, update before signing.
          </span>
        </div>
      )}

      {/* What you're signing — disclosure up top */}
      <div style={{
        background: "var(--color-elevated)",
        border: "1px solid var(--color-border)",
        borderRadius: 10, padding: "14px 16px", marginBottom: 18,
      }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          gap: 10, marginBottom: 8,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)" }}>
            What you&apos;re agreeing to
          </div>
          <button
            type="button"
            onClick={() => setPreviewOpen(true)}
            style={{
              background: "transparent",
              border: `1px solid ${accent}`,
              borderRadius: 6,
              padding: "5px 10px",
              fontSize: 11, fontWeight: 700, letterSpacing: "0.04em",
              color: accent,
              cursor: "pointer",
              display: "inline-flex", alignItems: "center", gap: 4,
            }}
          >
            <FileText size={11} /> Preview
          </button>
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
          Tap <strong>Preview</strong> above to read the full document now, or review on the next screen before signing.
        </p>
      </div>

      {previewOpen && (
        <PaperworkPreviewModal
          accent={accent}
          onClose={() => setPreviewOpen(false)}
        />
      )}

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

      <Section title="Tax info (W-9)">
        <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--color-border-subtle)" }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
            Federal tax classification<span style={{ color: accent, marginLeft: 3 }}>*</span>
          </div>
          <select
            value={form.tax_classification}
            onChange={set("tax_classification")}
            style={{
              ...inputStyle,
              appearance: "none", WebkitAppearance: "none",
              backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>")`,
              backgroundRepeat: "no-repeat", backgroundPosition: "right 12px center", paddingRight: 34,
            }}
          >
            <option value="individual">Individual / Sole proprietor / Single-member LLC</option>
            <option value="c_corp">C Corporation</option>
            <option value="s_corp">S Corporation</option>
            <option value="partnership">Partnership</option>
            <option value="trust_estate">Trust / Estate</option>
            <option value="llc">Limited Liability Company</option>
            <option value="other">Other</option>
          </select>
        </div>
        {form.tax_classification === "llc" && (
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              LLC tax classification (C / S / P)<span style={{ color: accent, marginLeft: 3 }}>*</span>
            </div>
            <input
              maxLength={1}
              placeholder="C, S, or P"
              value={form.llc_class}
              onChange={e => setForm(prev => ({ ...prev, llc_class: e.target.value.toUpperCase().replace(/[^CSP]/g, "") }))}
              style={{ ...inputStyle, textTransform: "uppercase" }}
            />
          </div>
        )}
        {form.tax_classification === "other" && (
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--color-border-subtle)" }}>
            <Field label="Other classification (describe)" fieldKey="other_classification" placeholder="e.g. 501(c)(3) nonprofit" />
          </div>
        )}
        <Field label="Business name (if different from legal name)" fieldKey="business_name" placeholder="Optional — DBA / single-member LLC name" />
        <TwoCol>
          <div style={{ padding: "12px 14px", borderRight: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              TIN type<span style={{ color: accent, marginLeft: 3 }}>*</span>
            </div>
            <select
              value={form.tin_type}
              onChange={set("tin_type")}
              style={{
                ...inputStyle, appearance: "none", WebkitAppearance: "none",
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>")`,
                backgroundRepeat: "no-repeat", backgroundPosition: "right 12px center", paddingRight: 34,
              }}
            >
              <option value="ssn">SSN (Social Security Number)</option>
              <option value="ein">EIN (Employer ID Number)</option>
            </select>
          </div>
          <div style={{ padding: "12px 14px" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              {form.tin_type === "ssn" ? "SSN" : "EIN"}<span style={{ color: accent, marginLeft: 3 }}>*</span>
            </div>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="off"
              placeholder={form.tin_type === "ssn" ? "123-45-6789" : "12-3456789"}
              value={form.tin_type === "ssn" ? formatSsn(form.tin) : formatEin(form.tin)}
              onChange={e => setForm(prev => ({ ...prev, tin: e.target.value.replace(/\D/g, "").slice(0, 9) }))}
              style={{ ...inputStyle, fontFamily: "var(--font-mono)", letterSpacing: "0.05em" }}
            />
            {tinDigits.length > 0 && tinDigits.length !== 9 && (
              <div style={{ fontSize: 11, color: "#f87171", marginTop: 4 }}>Need 9 digits — got {tinDigits.length}</div>
            )}
          </div>
        </TwoCol>
        <TwoCol>
          <Field label="Exempt payee code (if any)" fieldKey="exempt_payee_code" placeholder="Optional" />
          <div style={{ padding: "12px 14px", borderTop: "1px solid var(--color-border-subtle)" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-muted)", marginBottom: 5 }}>
              FATCA reporting code (if any)
            </div>
            <input placeholder="Optional" value={form.fatca_code} onChange={set("fatca_code")} style={inputStyle} />
          </div>
        </TwoCol>
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
    </FormCtx.Provider>
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

// ─── SignAgreementStep — read the contract verbatim, draw a signature ─────────
//
// This replaces the old ReviewCard + iframe-PDF flow. Talent reads the full
// agreement (cover + W-9 summary + Sections 1–11 + 2257 disclosure) inline,
// scrolls to the bottom, draws a signature on a canvas, and submits. We POST
// the form data + base64 signature PNG to /api/compliance/shoots/{id}/sign;
// the server generates the merged IRS-W-9 + agreement PDF and pushes it to
// the scene's MEGA legal folder.

function SignAgreementStep({
  talentDisplay,
  talentRoleLabel,
  accent,
  shootDate,
  formData,
  signaturePng,
  onSignatureChange,
  submitting,
  error,
  onBack,
  onSubmit,
}: {
  talentDisplay: string
  talentRoleLabel: string
  accent: string
  shootDate: string
  formData: TalentFormData
  signaturePng: string | null
  onSignatureChange: (png: string | null) => void
  submitting: boolean
  error: string | null
  onBack: () => void
  onSubmit: () => void
}) {
  const [acknowledged, setAcknowledged] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const scrollerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    const handler = () => {
      // require talent to scroll to within 32px of the bottom at least once
      const remaining = el.scrollHeight - el.scrollTop - el.clientHeight
      if (remaining < 32) setScrolled(true)
    }
    el.addEventListener("scroll", handler, { passive: true })
    return () => el.removeEventListener("scroll", handler)
  }, [])

  const canSubmit = scrolled && acknowledged && !!signaturePng && !submitting
  const longDate = formatLongDate(shootDate)
  const tinFmt = formData.tin_type === "ssn" ? formatSsn(formData.tin) : formatEin(formData.tin)
  const fullAddress = [formData.street_address, formData.city_state_zip].filter(Boolean).join(", ")

  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
        Read &amp; Sign — {talentDisplay} ({talentRoleLabel})
      </div>
      <p style={{ fontSize: 13, color: "var(--color-text-faint)", marginBottom: 12, lineHeight: 1.5 }}>
        Read the full agreement. Scroll to the bottom, check the acknowledgement, draw your signature, and tap submit.
      </p>

      {/* Scrollable contract */}
      <div
        ref={scrollerRef}
        style={{
          height: "55vh", minHeight: 360, overflow: "auto",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 12, padding: "20px 22px", marginBottom: 14,
          fontSize: 13.5, lineHeight: 1.6, color: "var(--color-text)",
        }}
      >
        {/* SECTION 01 — IRS W-9 summary */}
        <SectionEyebrow accent={accent} text="Section 01 of 03 · IRS Form W-9" />
        <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>Taxpayer Identification &amp; Certification</h3>
        <p style={{ color: "var(--color-text-muted)", fontSize: 12.5, marginBottom: 10 }}>
          The values below appear on the official IRS Form W-9 included in your final PDF.
        </p>
        <FactGrid rows={[
          ["Legal name", formData.legal_name],
          ["Business name", formData.business_name || "—"],
          ["Tax classification", taxClassLabel(formData)],
          ["Address", fullAddress || "—"],
          [formData.tin_type === "ssn" ? "SSN" : "EIN", tinFmt],
        ]} />

        {/* SECTION 02 — Model Services Agreement */}
        <SectionEyebrow accent={accent} text="Section 02 of 03 · Model Services Agreement" />
        <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>{CONTRACT_TITLE}</h3>
        <p style={{ marginBottom: 10 }}>{CONTRACT_INTRO}</p>
        {AGREEMENT_SECTIONS.map(sec => (
          <div key={sec.id} style={{ marginBottom: 14 }}>
            <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: "12px 0 4px" }}>{sec.heading}</h4>
            {sec.body.split("\n\n").map((p, i) => (
              <p key={i} style={{ marginBottom: 6 }}>{p}</p>
            ))}
          </div>
        ))}
        <p style={{ fontStyle: "italic", color: "var(--color-text-muted)", marginBottom: 6 }}>{WITNESS_STATEMENT}</p>
        <p style={{ color: "var(--color-text-muted)", fontSize: 12.5, marginBottom: 16 }}>{EXECUTION_LINE}</p>

        {/* SECTION 03 — 2257 Records */}
        <SectionEyebrow accent={accent} text="Section 03 of 03 · 18 U.S.C. § 2257 Records" />
        <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>{DISCLOSURE_HEADING}</h3>
        <p style={{ marginBottom: 6 }}>
          <strong>Production:</strong> {PRODUCER_NAME} studio production · <strong>Date:</strong> {longDate}
        </p>
        <p style={{ marginBottom: 12 }}>
          I, <strong>{formData.legal_name}</strong>, {DISCLOSURE_STATEMENT.replace(/^I\s+/, "").replace(/^I,\s+/, "")}
        </p>
        <FactGrid rows={[
          ["Full legal name", formData.legal_name],
          ["Date of birth", formatDob(formData.dob)],
          ["Place of birth", formData.place_of_birth || "—"],
          ["Residential address", fullAddress || "—"],
          ["Primary ID", formData.id1_type ? `${formData.id1_type} · ${formData.id1_number}` : "—"],
          ["Secondary ID", formData.id2_type ? `${formData.id2_type} · ${formData.id2_number}` : "—"],
          ["Phone", formData.phone || "—"],
          ["Email", formData.email || "—"],
          ["Stage names", formData.stage_name || talentDisplay],
        ]} />
        <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: "12px 0 4px" }}>{DOCUMENTS_PROVIDED_HEADING}</h4>
        {DOCUMENTS_PROVIDED_LIST.map((item, i) => (
          <p key={i} style={{ marginBottom: 4 }}>{item}</p>
        ))}
        <p style={{ marginTop: 14, marginBottom: 10 }}>{DATA_CONSENT}</p>
        <p style={{ marginBottom: 10 }}>{PERJURY_STATEMENT}</p>
        <p style={{ color: "var(--color-text-muted)", fontSize: 12.5 }}>{INDEMNITY_STATEMENT}</p>

        <div style={{ marginTop: 18, paddingTop: 14, borderTop: "1px solid var(--color-border-subtle)", color: "var(--color-text-faint)", fontSize: 11.5 }}>
          End of document — please scroll up to review any section before signing.
        </div>
      </div>

      {/* Read-progress hint */}
      {!scrolled && (
        <div style={{
          marginBottom: 12, padding: "9px 12px", borderRadius: 8,
          background: "rgba(255,255,255,0.04)", border: "1px solid var(--color-border-subtle)",
          fontSize: 12, color: "var(--color-text-muted)",
        }}>
          Scroll the document above to the end to enable signing.
        </div>
      )}

      {/* Acknowledgement */}
      <label style={{
        display: "flex", alignItems: "flex-start", gap: 10,
        padding: "10px 12px", marginBottom: 12,
        background: acknowledged ? "rgba(190,214,47,0.06)" : "var(--color-elevated)",
        border: `1px solid ${acknowledged ? "rgba(190,214,47,0.3)" : "var(--color-border)"}`,
        borderRadius: 10,
        cursor: scrolled ? "pointer" : "not-allowed",
        opacity: scrolled ? 1 : 0.5,
      }}>
        <input
          type="checkbox"
          checked={acknowledged}
          disabled={!scrolled}
          onChange={e => setAcknowledged(e.target.checked)}
          style={{ width: 18, height: 18, marginTop: 1, flexShrink: 0, accentColor: "var(--color-lime)" }}
        />
        <span style={{ fontSize: 13, color: "var(--color-text)", lineHeight: 1.45 }}>
          I have read all three sections above and I confirm the information is accurate. I am signing
          the W-9 certification, the Model Services Agreement, and the 18 U.S.C. § 2257 disclosure.
        </span>
      </label>

      {/* Signature pad */}
      <div style={{
        background: "var(--color-elevated)", border: "1px solid var(--color-border)",
        borderRadius: 12, padding: "14px 14px 12px", marginBottom: 14,
      }}>
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: 8,
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.06em",
                        textTransform: "uppercase", color: "var(--color-text-muted)" }}>
            Talent signature — {talentDisplay}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-faint)" }}>{longDate}</div>
        </div>
        <SignaturePad onChange={onSignatureChange} accent={accent} disabled={!scrolled || !acknowledged} />
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
          onClick={onBack}
          disabled={submitting}
          style={{
            background: "transparent", border: "1px solid var(--color-border)",
            borderRadius: 10, padding: "14px 18px",
            fontSize: 14, fontWeight: 600,
            color: "var(--color-text-muted)",
            cursor: submitting ? "not-allowed" : "pointer",
          }}
        >
          ← Edit details
        </button>
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          style={{
            flex: 1,
            background: canSubmit ? "var(--color-lime)" : "var(--color-elevated)",
            border: "none", borderRadius: 10, padding: "16px 20px",
            fontSize: 15, fontWeight: 700,
            color: canSubmit ? "#000" : "var(--color-text-faint)",
            cursor: canSubmit ? "pointer" : "not-allowed",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          }}
        >
          {submitting
            ? <><Loader2 size={16} className="animate-spin" /> Saving signature…</>
            : !scrolled
              ? <>Scroll to bottom to enable</>
              : !acknowledged
                ? <>Check the box above</>
                : !signaturePng
                  ? <>Draw signature above</>
                  : <><CheckCircle2 size={16} /> Sign &amp; Submit Agreement</>
          }
        </button>
      </div>
    </div>
  )
}

// ─── PaperworkPreviewModal — read the contract before filling out the form ───
//
// Surfaces the same verbatim contract content used on the Sign step, but
// without any form-data fields (no SSN, no DOB, no addresses) — talent can
// preview what they're signing while the form is still being filled. Live
// data appears on the Sign step where it's interleaved with the agreement.

function PaperworkPreviewModal({
  accent,
  onClose,
}: {
  accent: string
  onClose: () => void
}) {
  // Lock body scroll while the modal is open and close on ESC
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener("keydown", onKey)
    }
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Paperwork preview"
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.65)",
        backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--color-bg)",
          border: "1px solid var(--color-border)",
          borderRadius: 14,
          width: "min(720px, 100%)",
          maxHeight: "min(86vh, 920px)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          boxShadow: "0 24px 60px rgba(0,0,0,0.55)",
        }}
      >
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "14px 18px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface)",
        }}>
          <FileText size={16} color={accent} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
              Paperwork preview
            </div>
            <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 1 }}>
              W-9 · Model Services Agreement · 18 U.S.C. § 2257 disclosure
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close preview"
            style={{
              background: "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: "6px 8px",
              cursor: "pointer",
              color: "var(--color-text-muted)",
              display: "inline-flex", alignItems: "center",
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Scrollable contract body */}
        <div style={{
          flex: 1, overflow: "auto",
          padding: "20px 22px",
          fontSize: 13.5, lineHeight: 1.6, color: "var(--color-text)",
        }}>
          <SectionEyebrow accent={accent} text="Section 01 of 03 · IRS Form W-9" />
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>Taxpayer Identification &amp; Certification</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: 12.5, marginBottom: 10 }}>
            Your final signed packet includes the official IRS Form W-9 with the legal name,
            address, federal tax classification, and SSN/EIN you enter on this form.
          </p>
          <ul style={{ margin: "4px 0 14px", paddingLeft: 18, color: "var(--color-text-muted)", fontSize: 12.5 }}>
            <li>Used by Eclatech&apos;s payment processor to issue 1099-NEC if applicable.</li>
            <li>Backup-withholding certification &amp; FATCA reporting code (most performers leave this blank).</li>
          </ul>

          <SectionEyebrow accent={accent} text="Section 02 of 03 · Model Services Agreement" />
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>{CONTRACT_TITLE}</h3>
          <p style={{ marginBottom: 10 }}>{CONTRACT_INTRO}</p>
          {AGREEMENT_SECTIONS.map(sec => (
            <div key={sec.id} style={{ marginBottom: 14 }}>
              <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: "12px 0 4px" }}>{sec.heading}</h4>
              {sec.body.split("\n\n").map((p, i) => (
                <p key={i} style={{ marginBottom: 6 }}>{p}</p>
              ))}
            </div>
          ))}
          <p style={{ fontStyle: "italic", color: "var(--color-text-muted)", marginBottom: 6 }}>{WITNESS_STATEMENT}</p>
          <p style={{ color: "var(--color-text-muted)", fontSize: 12.5, marginBottom: 16 }}>{EXECUTION_LINE}</p>

          <SectionEyebrow accent={accent} text="Section 03 of 03 · 18 U.S.C. § 2257 Records" />
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>{DISCLOSURE_HEADING}</h3>
          <p style={{ marginBottom: 12 }}>{DISCLOSURE_STATEMENT}</p>
          <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: "12px 0 4px" }}>{DOCUMENTS_PROVIDED_HEADING}</h4>
          {DOCUMENTS_PROVIDED_LIST.map((item, i) => (
            <p key={i} style={{ marginBottom: 4 }}>{item}</p>
          ))}
          <p style={{ marginTop: 14, marginBottom: 10 }}>{DATA_CONSENT}</p>
          <p style={{ marginBottom: 10 }}>{PERJURY_STATEMENT}</p>
          <p style={{ color: "var(--color-text-muted)", fontSize: 12.5 }}>{INDEMNITY_STATEMENT}</p>

          <div style={{
            marginTop: 18, paddingTop: 14,
            borderTop: "1px solid var(--color-border-subtle)",
            color: "var(--color-text-faint)", fontSize: 11.5,
          }}>
            Producer of record: {PRODUCER_NAME}. The agreement on the Sign step shows your details
            interleaved with this text — you&apos;ll have one more chance to review before signing.
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          display: "flex", justifyContent: "flex-end",
        }}>
          <button
            onClick={onClose}
            style={{
              background: accent,
              border: "none",
              borderRadius: 8,
              padding: "10px 18px",
              cursor: "pointer",
              color: "#000",
              fontSize: 13, fontWeight: 700,
              display: "inline-flex", alignItems: "center", gap: 6,
            }}
          >
            Got it — back to form
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── DriveImportModal — wire existing Drive paperwork into the shoot ────────
//
// One field: paste the Drive folder URL. The server walks the folder, matches
// PDFs to female/male by filename slug, copies bytes to MEGA, and inserts thin
// compliance_signatures rows. PII never touches the Hub UI — this modal only
// holds a folder URL and a status string.

function DriveImportModal({
  accent,
  url,
  onUrlChange,
  submitting,
  error,
  onClose,
  onSubmit,
}: {
  accent: string
  url: string
  onUrlChange: (v: string) => void
  submitting: boolean
  error: string | null
  onClose: () => void
  onSubmit: () => void
}) {
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !submitting) onClose() }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener("keydown", onKey)
    }
  }, [onClose, submitting])

  const canSubmit = url.trim().length > 0 && !submitting

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Import from Drive folder"
      onClick={() => { if (!submitting) onClose() }}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.65)",
        backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--color-bg)",
          border: "1px solid var(--color-border)",
          borderRadius: 14,
          width: "min(560px, 100%)",
          display: "flex", flexDirection: "column", overflow: "hidden",
          boxShadow: "0 24px 60px rgba(0,0,0,0.55)",
        }}
      >
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "14px 18px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface)",
        }}>
          <FolderOpen size={16} color={accent} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
              Import from Drive folder
            </div>
            <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 1 }}>
              Pulls the signed PDFs into MEGA and marks talent as Signed.
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
            style={{
              background: "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: 8, padding: "6px 8px",
              cursor: submitting ? "not-allowed" : "pointer",
              color: "var(--color-text-muted)",
            }}
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", margin: 0, lineHeight: 1.55 }}>
            Paste the Drive folder URL containing the signed PDFs. The server will match each
            PDF to female / male talent by filename and copy the original byte-for-byte to MEGA.
            No new contract is generated.
          </p>

          <div>
            <div style={{
              fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
              textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 6,
            }}>
              Drive folder URL
            </div>
            <input
              autoFocus
              value={url}
              onChange={e => onUrlChange(e.target.value)}
              placeholder="https://drive.google.com/drive/folders/…"
              style={{
                width: "100%",
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                padding: "11px 14px",
                fontSize: 13, color: "var(--color-text)",
                outline: "none", boxSizing: "border-box",
                fontFamily: "var(--font-mono)",
              }}
            />
          </div>

          {error && (
            <div style={{
              background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8, padding: "10px 12px",
              fontSize: 12.5, color: "#f87171",
            }}>
              {error}
            </div>
          )}
        </div>

        <div style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          display: "flex", justifyContent: "flex-end", gap: 8,
        }}>
          <button
            onClick={onClose}
            disabled={submitting}
            style={{
              background: "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: 8, padding: "10px 14px",
              fontSize: 12.5, fontWeight: 600,
              color: "var(--color-text-muted)",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            disabled={!canSubmit}
            style={{
              background: canSubmit ? accent : "var(--color-elevated)",
              border: "none",
              borderRadius: 8, padding: "10px 18px",
              fontSize: 13, fontWeight: 700,
              color: canSubmit ? "#000" : "var(--color-text-faint)",
              cursor: canSubmit ? "pointer" : "not-allowed",
              display: "inline-flex", alignItems: "center", gap: 6,
            }}
          >
            {submitting
              ? <><Loader2 size={13} className="animate-spin" /> Importing…</>
              : <>Import paperwork</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

function SectionEyebrow({ accent, text }: { accent: string; text: string }) {
  return (
    <div style={{
      marginTop: 4, marginBottom: 10,
      paddingBottom: 8, borderBottom: `1px solid ${accent}33`,
    }}>
      <span style={{
        display: "inline-block", padding: "2px 8px", borderRadius: 4,
        background: `${accent}22`, color: accent, fontSize: 10, fontWeight: 700,
        letterSpacing: "0.12em", textTransform: "uppercase",
      }}>{text}</span>
    </div>
  )
}

function FactGrid({ rows }: { rows: [string, string][] }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 18px",
      background: "var(--color-elevated)", border: "1px solid var(--color-border-subtle)",
      borderRadius: 8, padding: "12px 14px", marginBottom: 14,
    }}>
      {rows.map(([label, value], i) => (
        <div key={i}>
          <div style={{
            fontSize: 9.5, fontWeight: 700, letterSpacing: "0.1em",
            textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 2,
          }}>{label}</div>
          <div style={{ fontSize: 13, color: "var(--color-text)", wordBreak: "break-word" }}>
            {value || "—"}
          </div>
        </div>
      ))}
    </div>
  )
}

function formatLongDate(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso + "T12:00:00")
  if (!Number.isFinite(d.getTime())) return iso
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
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

// Photo slots are female-talent-only by design. Male performers are recurring
// crew whose IDs live in a static Drive folder maintained by admin and
// referenced day-to-day; capturing them per-shoot is just churn.
function buildSlots(female: string, _male: string): PhotoSlot[] {
  return [
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
    {
      id: "signout-video",
      label: "signout-video.mp4",
      display: "Sign Out Video",
      talent: "female",
      category: "signout",
      required: true,
      fileType: "video",
    },
  ]
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
            <span style={{ fontSize: 12, color: "var(--color-text-muted)", textAlign: "center", lineHeight: 1.45 }}>
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

// ─── TalentPicker ─────────────────────────────────────────────────────────────
//
// Entry phase for the docs step. Surfaces both talents on the shoot side-by-
// side with their independent signing status. The staff picks which one to
// handle right now; flows are entirely separate and can be done in any order
// on different days. When both are signed, "Continue → Photos" advances the
// outer wizard to the photos/MEGA step.

function TalentPicker({
  shoot,
  accent,
  signed,
  onStartFemale,
  onStartMale,
  onAutoSignFemale,
  onAutoSignMale,
  autoSignFemaleStatus,
  autoSignMaleStatus,
  onEditSignature,
  onContinueToPhotos,
  onImportFromDrive,
}: {
  shoot: ComplianceShoot
  accent: string
  signed: SignedSummary[]
  onStartFemale: () => void
  onStartMale: () => void
  onAutoSignFemale: () => void
  onAutoSignMale: () => void
  autoSignFemaleStatus: "idle" | "running" | "no-prior" | "error"
  autoSignMaleStatus: "idle" | "running" | "no-prior" | "error"
  onEditSignature: (signatureId: number) => void
  onContinueToPhotos: () => void
  onImportFromDrive: () => void
}) {
  const femaleSigned = signed.find(s => s.talent_role === "female")
  const maleSigned   = signed.find(s => s.talent_role === "male")
  const needsMale    = !!shoot.male_talent
  const allSigned    = !!femaleSigned && (!needsMale || !!maleSigned)
  const longDate = formatLongDate(shoot.shoot_date)

  return (
    <div>
      {/* Shoot summary header */}
      <div style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 14, padding: "16px 18px", marginBottom: 14,
      }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: "0.14em",
          textTransform: "uppercase", color: accent, marginBottom: 6,
        }}>
          {shoot.studio || "Shoot"}{shoot.scene_id ? ` · ${shoot.scene_id}` : ""}
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--color-text)", lineHeight: 1.25 }}>
          {shoot.female_talent}
          {shoot.male_talent && (
            <>
              {" "}
              <span style={{ color: "var(--color-text-faint)", fontWeight: 500 }}>×</span>{" "}
              {shoot.male_talent}
            </>
          )}
        </div>
        <div style={{ fontSize: 12, color: "var(--color-text-faint)", marginTop: 4 }}>
          {longDate}
        </div>
      </div>

      {/* Per-talent cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 10, marginBottom: 14 }}>
        <div>
          <TalentSignCard
            role="Female"
            display={shoot.female_talent}
            accent={accent}
            signed={femaleSigned}
            shootId={shoot.shoot_id}
            slug={shoot.female_talent.replace(/ /g, "")}
            onStart={onStartFemale}
            onEdit={femaleSigned?.id ? () => onEditSignature(femaleSigned.id!) : undefined}
          />
          {/* Auto-fill: same back-to-back fast path as the male flow.
              Only when not yet signed. The prefill flow (form pre-populated
              with last shoot's values + sign step) is still available via
              "Sign →"; this button is the no-changes shortcut. */}
          {!femaleSigned && (
            <button
              type="button"
              onClick={onAutoSignFemale}
              disabled={autoSignFemaleStatus === "running"}
              style={{
                marginTop: 8,
                width: "100%",
                background: "transparent",
                border: "1px solid var(--color-border)",
                borderRadius: 8, padding: "10px 12px",
                fontSize: 12, fontWeight: 500,
                color: autoSignFemaleStatus === "no-prior"
                  ? "var(--color-text-faint)"
                  : "var(--color-text-muted)",
                cursor: autoSignFemaleStatus === "running" ? "wait" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              }}
              title="Apply her most recent paperwork to this shoot. No iPad signature needed."
            >
              {autoSignFemaleStatus === "running"
                ? "Auto-filling…"
                : autoSignFemaleStatus === "no-prior"
                ? `No prior paperwork on file for ${shoot.female_talent} — sign once first`
                : autoSignFemaleStatus === "error"
                ? "Auto-fill failed — try again"
                : `Auto-fill from prior paperwork`}
            </button>
          )}
        </div>
        {needsMale && (
          <div>
            <TalentSignCard
              role="Male"
              display={shoot.male_talent}
              accent={accent}
              signed={maleSigned}
              shootId={shoot.shoot_id}
              slug={shoot.male_talent.replace(/ /g, "")}
              onStart={onStartMale}
              onEdit={maleSigned?.id ? () => onEditSignature(maleSigned.id!) : undefined}
            />
            {/* Auto-fill: when the male shoots back-to-back the same paperwork
                applies. Server clones his most recent compliance_signatures row
                into this shoot — no iPad round-trip needed. Hidden once signed. */}
            {!maleSigned && (
              <button
                type="button"
                onClick={onAutoSignMale}
                disabled={autoSignMaleStatus === "running"}
                style={{
                  marginTop: 8,
                  width: "100%",
                  background: "transparent",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8, padding: "10px 12px",
                  fontSize: 12, fontWeight: 500,
                  color: autoSignMaleStatus === "no-prior"
                    ? "var(--color-text-faint)"
                    : "var(--color-text-muted)",
                  cursor: autoSignMaleStatus === "running" ? "wait" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                }}
                title="Apply the male's most recent paperwork to this shoot. No iPad signature needed."
              >
                {autoSignMaleStatus === "running"
                  ? "Auto-filling…"
                  : autoSignMaleStatus === "no-prior"
                  ? `No prior paperwork on file for ${shoot.male_talent} — sign once first`
                  : autoSignMaleStatus === "error"
                  ? "Auto-fill failed — try again"
                  : `Auto-fill from prior paperwork`}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Continue to photos — never blocked. Photos can be captured before
          talent signs paperwork (they sometimes finish paperwork later in
          the day), and they persist server-side regardless. */}
      <button
        onClick={onContinueToPhotos}
        style={{
          width: "100%",
          background: allSigned ? "var(--color-lime)" : "transparent",
          border: allSigned ? "none" : "1px solid var(--color-border)",
          borderRadius: 10, padding: "14px 18px",
          fontSize: 14, fontWeight: 700,
          color: allSigned ? "#000" : "var(--color-text)",
          cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
        }}
      >
        {allSigned
          ? <>Continue → Photos &amp; ID Capture</>
          : (() => {
              const total = needsMale ? 2 : 1
              const done = (femaleSigned ? 1 : 0) + (maleSigned ? 1 : 0)
              return <>{done}/{total} signed · Continue to Photos →</>
            })()
        }
      </button>
      {!allSigned && (
        <p style={{
          fontSize: 11.5, color: "var(--color-text-faint)",
          textAlign: "center", marginTop: 8, lineHeight: 1.5,
        }}>
          Paperwork can be completed later — capturing photos now is fine.
        </p>
      )}

      {/* Import existing Drive paperwork — for talent who already signed in
          the legacy flow and shouldn't have to re-sign on the iPad. */}
      {!allSigned && (
        <div style={{ marginTop: 12, textAlign: "center" }}>
          <button
            type="button"
            onClick={onImportFromDrive}
            style={{
              background: "transparent",
              border: "1px dashed var(--color-border)",
              borderRadius: 8,
              padding: "9px 14px",
              fontSize: 12, fontWeight: 600,
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "inline-flex", alignItems: "center", gap: 6,
            }}
          >
            <FolderOpen size={12} /> Import from Drive folder
          </button>
        </div>
      )}
    </div>
  )
}

function TalentSignCard({
  role,
  display,
  accent,
  signed,
  shootId,
  slug,
  onStart,
  onEdit,
}: {
  role: "Female" | "Male"
  display: string
  accent: string
  signed: SignedSummary | undefined
  shootId: string
  slug: string
  onStart: () => void
  onEdit?: () => void
}) {
  const isSigned = !!signed
  const pdfHref = isSigned
    ? `/api/compliance/${encodeURIComponent(shootId)}/pdf?talent=${encodeURIComponent(slug)}`
    : null

  return (
    <div style={{
      position: "relative",
      background: "var(--color-surface)",
      border: `1px solid ${isSigned ? "rgba(190,214,47,0.35)" : "var(--color-border)"}`,
      borderRadius: 14,
      padding: "16px 18px",
      display: "flex", alignItems: "center", gap: 14,
    }}>
      {/* Status dot — lime when signed, studio accent when waiting */}
      <div style={{
        width: 38, height: 38, borderRadius: "50%",
        background: isSigned
          ? "rgba(190,214,47,0.12)"
          : `color-mix(in oklab, ${accent} 14%, transparent)`,
        border: `1px solid ${isSigned ? "rgba(190,214,47,0.4)" : `color-mix(in oklab, ${accent} 35%, transparent)`}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        {isSigned
          ? <CheckCircle2 size={18} color="var(--color-lime)" />
          : <FileText size={16} color={accent} />
        }
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 9.5, fontWeight: 700, letterSpacing: "0.16em",
          textTransform: "uppercase", color: "var(--color-text-faint)",
          marginBottom: 2,
        }}>
          {role}
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)" }}>
          {display}
        </div>
        <div style={{ fontSize: 11.5, color: isSigned ? "var(--color-lime)" : "var(--color-text-muted)", marginTop: 2 }}>
          {isSigned
            ? <>Signed {formatRelativeTime(signed!.signed_at)} · {signed!.legal_name}</>
            : <>Not signed yet</>
          }
        </div>
      </div>

      <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
        {isSigned && pdfHref && (
          <a
            href={pdfHref}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              padding: "8px 12px", borderRadius: 8,
              background: "transparent", border: "1px solid var(--color-border)",
              fontSize: 12, fontWeight: 600,
              color: "var(--color-text-muted)", textDecoration: "none",
            }}
          >
            <ExternalLink size={11} /> View PDF
          </a>
        )}
        {isSigned && onEdit && (
          <button
            onClick={onEdit}
            type="button"
            title="Edit fields without re-signing — captures history"
            style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              padding: "8px 12px", borderRadius: 8,
              background: "transparent", border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Edit
          </button>
        )}
        <button
          onClick={onStart}
          style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            padding: "9px 14px", borderRadius: 8,
            background: isSigned ? "transparent" : "var(--color-lime)",
            border: isSigned ? "1px solid var(--color-border)" : "none",
            color: isSigned ? "var(--color-text)" : "#000",
            fontSize: 12, fontWeight: 700, cursor: "pointer",
          }}
        >
          {isSigned ? "Re-sign" : "Sign →"}
        </button>
      </div>
    </div>
  )
}

function formatRelativeTime(iso: string): string {
  if (!iso) return "—"
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return iso
  const diff = (Date.now() - then) / 1000
  if (diff < 60) return "just now"
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.round(diff / 86400)}d ago`
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}


// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  initialShoots: ComplianceShoot[]
  initialDate: string
  idToken: string | undefined
  loadError: string | null
}

type WizardStep = "select" | "docs" | "photos" | "upload"
type DocsPhase = "picker" | "female-form" | "female-sign" | "male-form" | "male-sign" | "done"

export function ComplianceView({ initialShoots, initialDate, idToken, loadError }: Props) {
  const client = api(idToken ?? null)

  // Date + shoot list state
  const [date, setDate] = useState(initialDate)
  const [shoots, setShoots] = useState<ComplianceShoot[]>(initialShoots)
  const [loading, setLoading] = useState(false)
  // Optional name search — when non-empty, the date filter is widened
  // server-side so the admin can find any talent across the recent year.
  const [searchQuery, setSearchQuery] = useState("")

  // Wizard state
  const [selected, setSelected] = useState<ComplianceShoot | null>(null)
  const [step, setStep] = useState<WizardStep>("select")

  // Docs step state
  // (legacy Drive-prepare flow — kept around because the photos/MEGA-sync
  // step still surfaces the Drive folder URL when one exists)
  const [prepResult, setPrepResult] = useState<CompliancePrepareResult | null>(null)
  // Per-talent flow: the wizard's "docs" step opens into a `picker` that
  // surfaces each talent's signing status independently. From there you can
  // start the female flow (form → sign → done) or the male flow, in any
  // order, on different days. Signing one returns to the picker.
  const [docsPhase, setDocsPhase] = useState<DocsPhase>("picker")
  const [signedSummary, setSignedSummary] = useState<SignedSummary[]>([])
  const [femaleSubmitting, setFemaleSubmitting] = useState(false)
  const [femaleError, setFemaleError] = useState<string | null>(null)
  const [maleSubmitting, setMaleSubmitting] = useState(false)
  const [maleError, setMaleError] = useState<string | null>(null)
  // Captured form data — held in memory so the signing step can pass it
  // through to /api/compliance/shoots/{id}/sign without a server round-trip.
  const [femaleFormData, setFemaleFormData] = useState<TalentFormData | null>(null)
  const [maleFormData, setMaleFormData] = useState<TalentFormData | null>(null)
  // Drawn signature (data: URL) and submit state for the sign step
  const [signaturePng, setSignaturePng] = useState<string | null>(null)
  const [signing, setSigning] = useState(false)
  const [signError, setSignError] = useState<string | null>(null)

  // Drive-import modal state (TKT-0152)
  const [driveImportOpen, setDriveImportOpen] = useState(false)
  const [driveImportUrl, setDriveImportUrl] = useState("")
  const [driveImportSubmitting, setDriveImportSubmitting] = useState(false)
  const [driveImportError, setDriveImportError] = useState<string | null>(null)

  // Auto-fill paperwork from prior shoots (TKT-0167) — separate state per
  // role because both can be in flight at once (different talent cards).
  const [autoSignMaleStatus, setAutoSignMaleStatus] = useState<
    "idle" | "running" | "no-prior" | "error"
  >("idle")
  const [autoSignFemaleStatus, setAutoSignFemaleStatus] = useState<
    "idle" | "running" | "no-prior" | "error"
  >("idle")

  // Edit-fields modal (TKT-0167) — set to a signature id to open
  const [editingSignatureId, setEditingSignatureId] = useState<number | null>(null)

  // Photos step state — locally captured (this session, not yet uploaded)
  const [photos, setPhotos] = useState<CapturedPhoto[]>([])
  // Server-persisted photos for the selected shoot. Loaded on entry so the
  // iPad sees thumbnails of anything uploaded on a previous visit. Photos
  // can be captured before talent has signed paperwork — they auto-upload
  // on capture so they're safe across reloads.
  const [savedPhotos, setSavedPhotos] = useState<CompliancePhoto[]>([])
  const [perSlotUploading, setPerSlotUploading] = useState<Record<string, boolean>>({})
  const [perSlotError, setPerSlotError] = useState<Record<string, string>>({})

  // Upload step state
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null)
  type FileStatus = { slotId: string; label: string; state: "idle" | "uploading" | "done" | "error"; error?: string }
  const [fileStatuses, setFileStatuses] = useState<FileStatus[]>([])
  const [uploadResult, setUploadResult] = useState<{ uploaded: string[]; errors: string[]; mega_paths: string[] } | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ status: string; message: string } | null>(null)

  const slots = selected ? buildSlots(selected.female_talent, selected.male_talent) : []

  // (postMessage cross-tab handoff used by the legacy /sign route is no
  // longer needed — signing happens inline in the wizard.)

  // ── Date fetch + name search ──────────────────────────────────────────

  async function loadDate(d: string, q?: string) {
    setLoading(true)
    try {
      const data = await client.compliance.shoots(d, q)
      setShoots(data)
    } catch (e) {
      setShoots([])
    } finally {
      setLoading(false)
    }
  }

  function handleDateChange(d: string) {
    setDate(d)
    setSearchQuery("")
    void loadDate(d)
  }

  function handleSearchChange(q: string) {
    setSearchQuery(q)
    if (q.trim()) {
      void loadDate(date, q)
    } else {
      void loadDate(date)
    }
  }

  // ── Select shoot ──────────────────────────────────────────────────────

  function selectShoot(shoot: ComplianceShoot) {
    setSelected(shoot)
    setStep("docs")
    setPrepResult(null)
    setDocsPhase("picker")
    setFemaleSubmitting(false)
    setFemaleError(null)
    setMaleSubmitting(false)
    setMaleError(null)
    setFemaleFormData(null)
    setMaleFormData(null)
    setSignaturePng(null)
    setSigning(false)
    setSignError(null)
    setSignedSummary([])
    setPhotos([])
    setSavedPhotos([])
    setPerSlotUploading({})
    setPerSlotError({})
    setUploadResult(null)
    setSyncResult(null)
    // Hydrate per-talent signed status from the API
    void client.compliance.signed(shoot.shoot_id).then(setSignedSummary).catch(() => setSignedSummary([]))
    // Load any photos uploaded for this shoot on a prior visit. Talent can
    // capture photos before signing — these persist server-side so they
    // re-appear here on next load.
    void client.compliance.listPhotos(shoot.shoot_id).then(setSavedPhotos).catch(() => setSavedPhotos([]))
    // If Drive folder already exists, pre-populate prep result state so the
    // photos step can still surface the Drive folder URL during cutover.
    if (shoot.drive_folder_id) {
      setPrepResult({
        folder_id: shoot.drive_folder_id,
        folder_url: shoot.drive_folder_url!,
        folder_name: shoot.drive_folder_name!,
        female_pdf_id: "",
        male_pdf_id: "",
        male_known: false,
        dates_filled: false,
        message: shoot.pdfs_ready ? "Signed documents on file" : "Folder already exists",
      })
    }
  }

  function exitWizard() {
    setSelected(null)
    setStep("select")
  }

  // ── Form submit handlers ──────────────────────────────────────────────
  // The form submits no longer go through fillForm/prepare — they just
  // capture the data into wizard state and transition to the sign step.
  // The actual server round-trip happens on signature submit (sign()).

  async function submitFemaleForm(data: TalentFormData) {
    if (!selected) return
    setFemaleError(null)
    setFemaleFormData(data)
    setSignaturePng(null)
    setSignError(null)
    setDocsPhase("female-sign")
  }

  async function submitMaleForm(data: TalentFormData) {
    if (!selected) return
    setMaleError(null)
    setMaleFormData(data)
    setSignaturePng(null)
    setSignError(null)
    setDocsPhase("male-sign")
  }

  // ── Auto-fill paperwork from prior shoot ──────────────────────────────
  // Lookup the talent's most recent compliance_signatures row + upsert
  // into this shoot. No iPad signature needed — typical for back-to-back
  // shoots where the talent's paperwork hasn't changed. Backend also
  // copies their ID photos from the prior shoot's Drive folder.
  async function handleAutoSignMale() {
    if (!selected) return
    setAutoSignMaleStatus("running")
    try {
      const result = await client.compliance.autoSignMale(selected.shoot_id)
      if (result.skipped_reason) {
        setAutoSignMaleStatus("no-prior")
        return
      }
      const updated = await client.compliance.signed(selected.shoot_id)
      setSignedSummary(updated)
      setAutoSignMaleStatus("idle")
    } catch {
      setAutoSignMaleStatus("error")
    }
  }

  async function handleAutoSignFemale() {
    if (!selected) return
    setAutoSignFemaleStatus("running")
    try {
      const result = await client.compliance.autoSignFemale(selected.shoot_id)
      if (result.skipped_reason) {
        setAutoSignFemaleStatus("no-prior")
        return
      }
      const updated = await client.compliance.signed(selected.shoot_id)
      setSignedSummary(updated)
      setAutoSignFemaleStatus("idle")
    } catch {
      setAutoSignFemaleStatus("error")
    }
  }

  // ── Sign handler — collects form + drawn PNG, POSTs to /sign ──────────

  async function submitSignature(role: "female" | "male") {
    if (!selected || !signaturePng) return
    const formData = role === "female" ? femaleFormData : maleFormData
    if (!formData) {
      setSignError("Form data missing — go back and fill the form")
      return
    }
    const slug = role === "female"
      ? selected.female_talent.replace(/ /g, "")
      : (selected.male_talent || "").replace(/ /g, "")
    const display = role === "female" ? selected.female_talent : selected.male_talent

    setSigning(true)
    setSignError(null)
    try {
      await client.compliance.sign(selected.shoot_id, {
        talent_role: role,
        talent_slug: slug,
        talent_display: display,
        legal_name: formData.legal_name,
        business_name: formData.business_name,
        tax_classification: formData.tax_classification,
        llc_class: formData.llc_class,
        other_classification: formData.other_classification,
        exempt_payee_code: formData.exempt_payee_code,
        fatca_code: formData.fatca_code,
        tin_type: formData.tin_type,
        tin: formData.tin,
        dob: formData.dob,
        place_of_birth: formData.place_of_birth,
        street_address: formData.street_address,
        city_state_zip: formData.city_state_zip,
        phone: formData.phone,
        email: formData.email,
        id1_type: formData.id1_type,
        id1_number: formData.id1_number,
        id2_type: formData.id2_type,
        id2_number: formData.id2_number,
        stage_names: formData.stage_name || display,
        signature_png: signaturePng,
      })
      void loadDate(date)
      // Clear the localStorage draft now that the data is durably saved on
      // the server. Form will start empty next time this shoot+role is opened.
      try {
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(`compliance-draft-${selected.shoot_id}-${role}`)
        }
      } catch {
        // Storage disabled — no harm leaving the draft around.
      }
      // Refresh per-talent signed status, then return to the picker so the
      // staff can either start the other talent's flow or move to photos.
      const fresh = await client.compliance.signed(selected.shoot_id).catch(() => [])
      setSignedSummary(fresh)
      setSignaturePng(null)
      if (role === "female") setFemaleFormData(null)
      else setMaleFormData(null)
      setDocsPhase("picker")
    } catch (e) {
      // Surface the HTTP status + body so we can actually debug. The default
      // Error.message often hides the real cause behind a generic string.
      let msg: string
      if (e instanceof ApiError) {
        const trimmed = (e.body || "").slice(0, 400)
        msg = `Server returned ${e.status}${trimmed ? ` — ${trimmed}` : ""}`
      } else {
        msg = e instanceof Error ? e.message : "Failed to save signature"
      }
      setSignError(msg)
      // Best-effort console trail for the on-call. Tap-to-copy from Safari dev
      // tools if the iPad is mirrored to a laptop.
      console.error("[compliance.sign]", { shoot_id: selected.shoot_id, role, error: e })
    } finally {
      setSigning(false)
    }
  }

  // ── Photo capture ─────────────────────────────────────────────────────
  // Photos are uploaded server-side IMMEDIATELY on capture so they survive
  // reloads — and so they can be captured before talent has signed any
  // paperwork. The legacy in-memory `photos` array is also kept around for
  // the upload step's progress-list rendering during this transition; the
  // saved-photo card is the source of truth once the round-trip succeeds.

  function capturePhoto(slot: PhotoSlot, file: File, preview: string) {
    setPhotos(prev => {
      const without = prev.filter(p => p.slotId !== slot.id)
      return [...without, { slotId: slot.id, label: slot.label, file, preview, fileType: slot.fileType }]
    })
    if (!selected) return
    setPerSlotUploading(prev => ({ ...prev, [slot.id]: true }))
    setPerSlotError(prev => { const next = { ...prev }; delete next[slot.id]; return next })
    void client.compliance.uploadPhotoV2(
      selected.shoot_id,
      file,
      slot.id,
      slot.label,
      slot.talent,
    ).then(saved => {
      setSavedPhotos(prev => {
        const without = prev.filter(p => p.slot_id !== slot.id)
        return [...without, saved]
      })
      void loadDate(date)
    }).catch((e: unknown) => {
      setPerSlotError(prev => ({ ...prev, [slot.id]: e instanceof Error ? e.message : "Upload failed" }))
    }).finally(() => {
      setPerSlotUploading(prev => { const next = { ...prev }; delete next[slot.id]; return next })
    })
  }

  function removePhoto(slotId: string) {
    setPhotos(prev => prev.filter(p => p.slotId !== slotId))
    if (!selected) return
    if (savedPhotos.some(p => p.slot_id === slotId)) {
      void client.compliance.deletePhotoV2(selected.shoot_id, slotId)
        .then(() => {
          setSavedPhotos(prev => prev.filter(p => p.slot_id !== slotId))
          void loadDate(date)
        })
        .catch(() => {/* leave row in place; show error inline next time */})
    }
  }

  // ── Upload ────────────────────────────────────────────────────────────

  async function uploadAll() {
    if (!selected || photos.length === 0) return
    setUploading(true)
    setUploadResult(null)
    setFileStatuses([])  // clear previous run before setting new statuses
    // Mark all files as "uploading" immediately — they all fire in parallel
    setFileStatuses(photos.map(p => ({ slotId: p.slotId, label: p.label, state: "uploading" as const })))
    setUploadProgress({ done: 0, total: photos.length })

    let done = 0
    const results = await Promise.allSettled(
      photos.map((photo, idx) => {
        const isVideo = photo.file.type.startsWith("video/")
        const timeoutMs = isVideo ? 600_000 : 120_000
        const abort = new AbortController()
        const timer = setTimeout(
          () => abort.abort(new DOMException(`Upload timed out after ${timeoutMs / 1000}s`, "TimeoutError")),
          timeoutMs,
        )
        return client.compliance.uploadPhoto(
          selected!.shoot_id,
          photo.file,
          photo.label,
          abort.signal,
        )
        .then(r => {
          const serverErr = r.errors?.find(e => e.includes(photo.label))
          setFileStatuses(prev => prev.map((s, j) =>
            j === idx ? { ...s, state: serverErr ? "error" as const : "done" as const, error: serverErr } : s
          ))
          return r
        })
        .catch((e: unknown) => {
          const msg = e instanceof Error ? e.message : "Upload failed"
          setFileStatuses(prev => prev.map((s, j) =>
            j === idx ? { ...s, state: "error" as const, error: msg } : s
          ))
          throw e
        })
        .finally(() => {
          clearTimeout(timer)
          done++
          setUploadProgress({ done, total: photos.length })
        })
      })
    )

    const uploaded: string[] = []
    const errors: string[] = []
    for (let i = 0; i < results.length; i++) {
      const res = results[i]
      if (res.status === "fulfilled") {
        uploaded.push(...res.value.uploaded)
        if (res.value.errors?.length) errors.push(...res.value.errors)
      } else {
        const msg = res.reason instanceof Error ? res.reason.message : "Upload failed"
        errors.push(`${photos[i].label}: ${msg}`)
      }
    }

    setUploadResult({ uploaded, errors, mega_paths: [] })
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

  // Paperwork flow — talent has the iPad and is filling out / signing.
  // The wizard hides crew chrome (header, "All Shoots" link, step dots) and
  // surfaces a LockBanner with a crew-PIN escape instead. Renders the form
  // and signing UI on a cream document surface.
  const inPaperFlow = step === "docs" && (
    docsPhase === "female-form" || docsPhase === "female-sign" ||
    docsPhase === "male-form"   || docsPhase === "male-sign"
  )

  return (
    <div style={{
      minHeight: "100vh", background: inPaperFlow ? "var(--color-doc-paper)" : "var(--color-bg)",
      padding: "0 0 80px",
      maxWidth: inPaperFlow ? "100%" : 720, margin: "0 auto",
    }}>

      {/* ── Header (hidden while talent is in paperwork flow) ── */}
      {!inPaperFlow && (
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
      )}

      {/* ── Step: Select ── */}
      {step === "select" && (
        <div style={{ padding: "16px 16px 0" }}>

          {/* Search by name — when non-empty, results expand across a year
              window so admins can find a specific talent's shoot. */}
          <div style={{ marginBottom: 10, position: "relative" }}>
            <input
              type="search"
              inputMode="search"
              autoComplete="off"
              spellCheck={false}
              placeholder="Search talent name…"
              value={searchQuery}
              onChange={e => handleSearchChange(e.target.value)}
              style={{
                width: "100%",
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                borderRadius: 10,
                padding: "11px 36px 11px 14px",
                fontSize: 13,
                color: "var(--color-text)",
                outline: "none",
                boxSizing: "border-box",
                fontFamily: "inherit",
              }}
            />
            {searchQuery && (
              <button
                onClick={() => handleSearchChange("")}
                aria-label="Clear search"
                style={{
                  position: "absolute", right: 8, top: 0, bottom: 0,
                  background: "transparent", border: "none",
                  color: "var(--color-text-faint)", cursor: "pointer",
                  display: "flex", alignItems: "center",
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Date navigation — hidden while searching */}
          {!searchQuery.trim() && (() => {
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

          {searchQuery.trim() && (
            <div style={{
              fontSize: 11, color: "var(--color-text-faint)", marginBottom: 12,
              letterSpacing: "0.04em",
            }}>
              Searching across the past year for "{searchQuery.trim()}" — clear to return to the day view.
            </div>
          )}

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
              No shoots for {new Date(date + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
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
                        {searchQuery.trim() && (
                          <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                            {formatLongDate(shoot.shoot_date)}
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
      {step === "docs" && selected && (() => {
        const paperRole =
          docsPhase === "female-form" || docsPhase === "female-sign" ? "female" :
          docsPhase === "male-form"   || docsPhase === "male-sign"   ? "male" : null
        const paperTalentName = paperRole === "female"
          ? selected.female_talent
          : paperRole === "male" ? (selected.male_talent || "") : ""
        const paperRoleLabel = paperRole === "female" ? "Female Talent" : paperRole === "male" ? "Male Talent" : ""
        const paperTitle =
          docsPhase === "female-form" || docsPhase === "male-form" ? "Talent Information" :
          docsPhase === "female-sign" || docsPhase === "male-sign" ? "Read & Sign Agreement" : ""
        return (
          <>
            {inPaperFlow && (
              <LockBanner
                onUnlock={() => { setDocsPhase("picker"); setSignError(null) }}
              />
            )}
            <div
              className={inPaperFlow ? "compliance-paper" : ""}
              style={inPaperFlow ? {
                padding: "0 0 60px",
                minHeight: "calc(100vh - 36px)",
                // Variable remap — Next/Turbopack drops `--var: ...` declarations
                // from non-:root selectors during the CSS pipeline, so we set
                // them inline here to override the dark-theme defaults for
                // every descendant inline `var(--color-*)` reference.
                ["--color-bg" as string]:            "var(--color-doc-paper)",
                ["--color-base" as string]:          "var(--color-doc-paper)",
                ["--color-surface" as string]:       "#ffffff",
                ["--color-elevated" as string]:      "#ffffff",
                ["--color-border" as string]:        "var(--color-doc-rule)",
                ["--color-border-subtle" as string]: "var(--color-doc-rule-faint)",
                ["--color-text" as string]:          "var(--color-doc-ink)",
                ["--color-text-muted" as string]:    "var(--color-doc-soft)",
                ["--color-text-faint" as string]:    "var(--color-doc-faint)",
              } : { padding: 16 }}
            >
              {inPaperFlow && paperTitle && (
                <div style={{ maxWidth: 580, margin: "0 auto", padding: "0 20px" }} className="doc-fadeup">
                  <Letterhead title={paperTitle} subtitle={paperTalentName ? `${paperTalentName} · ${paperRoleLabel}` : null} />
                </div>
              )}
              <div style={inPaperFlow ? { maxWidth: 580, margin: "0 auto", padding: "0 20px" } : undefined}>

          {/* Phase: talent picker — entry point. Each talent's flow is fully
              independent; the staff picks who to handle right now. */}
          {docsPhase === "picker" && (
            <TalentPicker
              shoot={selected}
              accent={accent}
              signed={signedSummary}
              onStartFemale={() => { setSignError(null); setFemaleError(null); setDocsPhase("female-form") }}
              onStartMale={() => { setSignError(null); setMaleError(null); setDocsPhase("male-form") }}
              onAutoSignFemale={handleAutoSignFemale}
              onAutoSignMale={handleAutoSignMale}
              autoSignFemaleStatus={autoSignFemaleStatus}
              autoSignMaleStatus={autoSignMaleStatus}
              onEditSignature={setEditingSignatureId}
              onContinueToPhotos={() => setStep("photos")}
              onImportFromDrive={() => {
                setDriveImportError(null)
                setDriveImportUrl("")
                setDriveImportOpen(true)
              }}
            />
          )}

          {editingSignatureId !== null && (
            <SignatureEditModal
              signatureId={editingSignatureId}
              idToken={idToken}
              onClose={() => setEditingSignatureId(null)}
              onSaved={async () => {
                if (selected) {
                  const fresh = await client.compliance.signed(selected.shoot_id).catch(() => [])
                  setSignedSummary(fresh)
                }
              }}
            />
          )}

          {driveImportOpen && (
            <DriveImportModal
              accent={accent}
              url={driveImportUrl}
              onUrlChange={setDriveImportUrl}
              submitting={driveImportSubmitting}
              error={driveImportError}
              onClose={() => { if (!driveImportSubmitting) setDriveImportOpen(false) }}
              onSubmit={async () => {
                if (!selected) return
                setDriveImportSubmitting(true)
                setDriveImportError(null)
                try {
                  const result: DriveImportResult = await client.compliance.importFromDrive(
                    selected.shoot_id,
                    driveImportUrl.trim(),
                  )
                  if (result.errors.length > 0 && result.imported.length === 0) {
                    setDriveImportError(result.errors.join("; "))
                    return
                  }
                  // Refresh signed summary + the global shoot list
                  const fresh = await client.compliance.signed(selected.shoot_id).catch(() => [])
                  setSignedSummary(fresh)
                  void loadDate(date)
                  setDriveImportOpen(false)
                } catch (e) {
                  setDriveImportError(e instanceof Error ? e.message : "Import failed")
                } finally {
                  setDriveImportSubmitting(false)
                }
              }}
            />
          )}

          {/* Female: form → sign */}
          {docsPhase === "female-form" && (
            <TalentForm
              talentLabel={`${selected.female_talent} — Female Talent`}
              accent={accent}
              submitting={femaleSubmitting}
              error={femaleError}
              onSubmit={submitFemaleForm}
              onBack={() => setDocsPhase("picker")}
              draftKey={`compliance-draft-${selected.shoot_id}-female`}
              prefillSource={{
                talentSlug: selected.female_talent.replace(/ /g, ""),
                role: "female",
                idToken,
                withinDays: 365,
              }}
            />
          )}
          {docsPhase === "female-sign" && femaleFormData && (
            <SignAgreementStep
              talentDisplay={selected.female_talent}
              talentRoleLabel="Female"
              accent={accent}
              shootDate={selected.shoot_date}
              formData={femaleFormData}
              signaturePng={signaturePng}
              onSignatureChange={setSignaturePng}
              submitting={signing}
              error={signError}
              onBack={() => { setDocsPhase("female-form"); setSignError(null) }}
              onSubmit={() => submitSignature("female")}
            />
          )}

          {/* Male: form → sign */}
          {docsPhase === "male-form" && selected.male_talent && (
            <TalentForm
              talentLabel={`${selected.male_talent} — Male Talent`}
              accent={accent}
              submitting={maleSubmitting}
              error={maleError}
              onSubmit={submitMaleForm}
              onBack={() => setDocsPhase("picker")}
              draftKey={`compliance-draft-${selected.shoot_id}-male`}
            />
          )}
          {docsPhase === "male-sign" && maleFormData && selected.male_talent && (
            <SignAgreementStep
              talentDisplay={selected.male_talent}
              talentRoleLabel="Male"
              accent={accent}
              shootDate={selected.shoot_date}
              formData={maleFormData}
              signaturePng={signaturePng}
              onSignatureChange={setSignaturePng}
              submitting={signing}
              error={signError}
              onBack={() => { setDocsPhase("male-form"); setSignError(null) }}
              onSubmit={() => submitSignature("male")}
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
            </div>
          </>
        )
      })()}

      {/* ── Step: Photos ── */}
      {step === "photos" && selected && (() => {
        // Resolve a slot's captured/saved state in one place. In-memory
        // captures (this session) win over server-saved photos so retakes
        // show the new image immediately even before upload completes.
        const capturedFor = (slotId: string): CapturedPhoto | undefined => {
          const inMem = photos.find(p => p.slotId === slotId)
          if (inMem) return inMem
          const saved = savedPhotos.find(p => p.slot_id === slotId)
          if (!saved) return undefined
          return {
            slotId: saved.slot_id,
            label: saved.label,
            // Re-render only — the bytes already live on the server, so we
            // just need a placeholder File for the in-memory shape.
            file: new File([], saved.label, { type: saved.mime_type }),
            preview: saved.url,
            fileType: saved.mime_type.startsWith("video/") ? "video" : "image",
          }
        }
        const slotIsDone = (slotId: string) => !!capturedFor(slotId)
        return (
        <div style={{ padding: 16 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
            ID &amp; Verification Photos
          </h2>
          <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginBottom: 16, lineHeight: 1.4 }}>
            Capture IDs and bunny-ear shots for each talent. Photos save automatically and reappear on the next visit.
          </p>

          {/* Female section */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: accent, marginBottom: 10 }}>
              {selected.female_talent}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {slots.filter(s => s.talent === "female" && s.category !== "signout").map(slot => {
                const captured = capturedFor(slot.id)
                const uploading = perSlotUploading[slot.id]
                const error = perSlotError[slot.id]
                return (
                  <div key={slot.id}>
                    <CameraButton
                      slot={slot}
                      captured={captured}
                      onCapture={(file, preview) => capturePhoto(slot, file, preview)}
                    />
                    {uploading && (
                      <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4, display: "flex", alignItems: "center", gap: 4 }}>
                        <Loader2 size={10} className="animate-spin" /> Saving…
                      </div>
                    )}
                    {error && (
                      <div style={{ fontSize: 10, color: "#f87171", marginTop: 4 }}>{error}</div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Sign Out Video */}
          {(() => {
            const videoSlot = slots.find(s => s.category === "signout")
            if (!videoSlot) return null
            const captured = capturedFor(videoSlot.id)
            const uploading = perSlotUploading[videoSlot.id]
            const error = perSlotError[videoSlot.id]
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
                {uploading && (
                  <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4, display: "flex", alignItems: "center", gap: 4 }}>
                    <Loader2 size={10} className="animate-spin" /> Saving…
                  </div>
                )}
                {error && (
                  <div style={{ fontSize: 10, color: "#f87171", marginTop: 4 }}>{error}</div>
                )}
              </div>
            )
          })()}

          {/* Required check */}
          {(() => {
            const required = slots.filter(s => s.required)
            const done = required.filter(s => slotIsDone(s.id))
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
                      {required.filter(s => !slotIsDone(s.id)).map(s => s.display).join(", ")} still needed
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
              disabled={photos.length === 0 && savedPhotos.length === 0}
              style={{
                flex: 1,
                background: (photos.length + savedPhotos.length) > 0 ? accent : "var(--color-elevated)",
                border: "none", borderRadius: 10, padding: "16px 20px",
                fontSize: 15, fontWeight: 700,
                color: (photos.length + savedPhotos.length) > 0 ? "#000" : "var(--color-text-faint)",
                cursor: (photos.length + savedPhotos.length) > 0 ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              }}
            >
              Continue to Upload <ChevronRight size={16} />
            </button>
          </div>
        </div>
        )
      })()}

      {/* ── Step: Upload ── */}
      {step === "upload" && selected && (
        <div style={{ padding: 16 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--color-text-faint)", marginBottom: 4 }}>
            Upload &amp; File
          </h2>
          <p style={{ fontSize: 12, color: "var(--color-text-faint)", marginBottom: 16, lineHeight: 1.4 }}>
            Upload all photos to the Drive legal folder, then copy the complete package to MEGA.
          </p>

          {/* File list — shows idle grid before upload, per-file status during/after */}
          <div style={{
            background: "var(--color-surface)", border: "1px solid var(--color-border)",
            borderRadius: 12, overflow: "hidden", marginBottom: 14,
          }}>
            {/* Progress bar — only visible while uploading */}
            {uploading && uploadProgress && (
              <div style={{ height: 3, background: "var(--color-elevated)", overflow: "hidden" }}>
                <div style={{
                  height: "100%",
                  width: "100%",
                  background: "var(--color-lime)",
                  transformOrigin: "left",
                  transform: `scaleX(${uploadProgress.done / Math.max(1, uploadProgress.total)})`,
                  transition: "transform 300ms ease",
                }} />
              </div>
            )}

            <div style={{ padding: 14 }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: "var(--color-text-faint)",
                letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10,
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <span>Photos to Upload ({photos.length})</span>
                {uploading && uploadProgress && (
                  <span style={{ color: "var(--color-lime)", fontVariantNumeric: "tabular-nums" }}>
                    {uploadProgress.done} / {uploadProgress.total}
                  </span>
                )}
              </div>

              {/* When not uploading: thumbnail grid with remove buttons */}
              {!uploading && fileStatuses.length === 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
                  {photos.map(p => (
                    <div key={p.slotId} style={{ position: "relative", aspectRatio: "1", borderRadius: 8, overflow: "hidden" }}>
                      {p.fileType === "video" ? (
                        <div style={{
                          width: "100%", height: "100%", background: "var(--color-elevated)",
                          display: "flex", flexDirection: "column",
                          alignItems: "center", justifyContent: "center", gap: 4,
                        }}>
                          <Video size={18} color="var(--color-lime)" />
                          <span style={{ fontSize: 9, color: "var(--color-text-faint)", textAlign: "center", padding: "0 4px" }}>{p.label}</span>
                        </div>
                      ) : (
                        <img src={p.preview} alt={p.label} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      )}
                      <button onClick={() => removePhoto(p.slotId)} style={{
                        position: "absolute", top: 3, right: 3,
                        background: "rgba(0,0,0,0.6)", border: "none", borderRadius: "50%",
                        width: 20, height: 20, cursor: "pointer", color: "#fff",
                        display: "flex", alignItems: "center", justifyContent: "center", padding: 0,
                      }}>
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* During/after upload: per-file status rows */}
              {fileStatuses.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {fileStatuses.map((fs, i) => {
                    const photo = photos[i]
                    const isDone    = fs.state === "done"
                    const isError   = fs.state === "error"
                    const isActive  = fs.state === "uploading"
                    return (
                      <div key={fs.slotId} style={{
                        display: "flex", alignItems: "center", gap: 10,
                        padding: "7px 10px", borderRadius: 8,
                        background: isDone  ? "rgba(190,214,47,0.06)"
                                  : isError ? "rgba(239,68,68,0.06)"
                                  : isActive ? "rgba(255,255,255,0.03)"
                                  : "transparent",
                        transition: "background 0.2s",
                      }}>
                        {/* Thumbnail / video icon */}
                        <div style={{
                          width: 32, height: 32, borderRadius: 6, overflow: "hidden",
                          flexShrink: 0, background: "var(--color-elevated)",
                        }}>
                          {photo?.fileType === "video" ? (
                            <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                              <Video size={14} color="var(--color-lime)" />
                            </div>
                          ) : photo?.preview ? (
                            <img src={photo.preview} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                          ) : null}
                        </div>

                        {/* Label + error */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: 12, fontWeight: 500,
                            color: isDone ? "var(--color-text)" : isError ? "#f87171" : "var(--color-text-muted)",
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          }}>
                            {fs.label}
                          </div>
                          {isError && fs.error && (
                            <div style={{ fontSize: 10, color: "#f87171", marginTop: 1, opacity: 0.8 }}>
                              {fs.error.replace(`${fs.label}: `, "")}
                            </div>
                          )}
                        </div>

                        {/* Status icon */}
                        <div style={{ flexShrink: 0, width: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {isActive && <Loader2 size={14} className="animate-spin" color="var(--color-text-faint)" />}
                          {isDone  && <CheckCircle2 size={14} color="#bed62f" />}
                          {isError && <X size={14} color="#f87171" />}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Upload summary (shown after completion, errors only if any) */}
          {uploadResult && uploadResult.errors.length === 0 && uploadResult.uploaded.length > 0 && (
            <div style={{
              background: "rgba(190,214,47,0.08)", border: "1px solid rgba(190,214,47,0.25)",
              borderRadius: 10, padding: "10px 14px", marginBottom: 14,
              display: "flex", alignItems: "center", gap: 8, fontSize: 13,
              color: "var(--color-lime)",
            }}>
              <CheckCircle2 size={14} />
              {uploadResult.uploaded.length} file{uploadResult.uploaded.length !== 1 ? "s" : ""} uploaded to Drive
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
                    {uploadProgress && uploadProgress.done < uploadProgress.total
                      ? `${uploadProgress.total - uploadProgress.done} remaining…`
                      : "Finishing…"}
                  </>
                : uploadResult && uploadResult.errors.length > 0 && uploadResult.uploaded.length === 0
                  ? <><Upload size={16} /> Retry Upload</>
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
