"use client"

import { useEffect, useState, useMemo } from "react"
import { createPortal } from "react-dom"
import Link from "next/link"
import { X, ChevronDown, ChevronUp, FileText, ClipboardCheck } from "lucide-react"
import { api, type Shoot, type Script, type LegalDocFile, type LegalDocsResult, type ComplianceShoot, SHOOT_ASSET_ORDER, SHOOT_ASSET_LABELS } from "@/lib/api"
import { useIdToken } from "@/hooks/use-id-token"
import { studioAbbr, studioColor } from "@/lib/studio-colors"

/** Detail modal shared by the week and month calendars. */
export function ShootModal({ shoot, onClose }: { shoot: Shoot; onClose: () => void }) {
  // We portal to <body> because the hub's page-entrance `fadeIn` animation
  // leaves a lingering transform on an ancestor of <main>, which creates a
  // containing block for position:fixed — that's why this modal rendered
  // with its top below the viewport edge when left in-place. Portalling
  // escapes the transformed parent so `inset: 0` means "viewport" again.
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  // Pull the script(s) backing this shoot. Scripts live per (studio + date +
  // talent) tuple, so a multi-scene shoot can return 1–N scripts depending on
  // how the day was split. We fetch per-studio to avoid blasting the whole
  // sheet, then match locally by date + talent.
  const idToken = useIdToken(undefined)
  const [scripts, setScripts] = useState<Script[]>([])
  const [scriptsLoading, setScriptsLoading] = useState(true)
  // Per-script expansion — each ScriptCard manages its own state so directors
  // can drill into one scene without unfurling the others.
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  // Per-scene expansion for asset detail grid
  const [expandedScenes, setExpandedScenes] = useState<Set<string>>(new Set())
  // Legal docs fetched from Drive for the W9 display in TalentRow
  const [legalDocs, setLegalDocs] = useState<LegalDocsResult | null>(null)
  // Compliance status for this shoot
  const [complianceShoot, setComplianceShoot] = useState<ComplianceShoot | null | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    setScriptsLoading(true)
    const client = api(idToken ?? null)
    const studios = Array.from(new Set(shoot.scenes.map(sc => sc.studio).filter(Boolean)))
    const targetDate = (shoot.shoot_date || "").slice(0, 10)
    Promise.all(studios.map(studio => client.scripts.list({ studio }).catch(() => [] as Script[])))
      .then(lists => {
        if (cancelled) return
        // Dedupe by id — the dev-mock endpoint ignores the studio filter, and
        // even in prod a script can surface under two studios when scenes span
        // tabs. Last write wins (both rows are the same).
        const byId = new Map<number, Script>()
        for (const s of lists.flat()) byId.set(s.id, s)
        const matched = Array.from(byId.values()).filter(s =>
          normalizeDate(s.shoot_date || "") === targetDate &&
          (!shoot.female_talent || s.female.trim().toLowerCase() === shoot.female_talent.trim().toLowerCase()) &&
          (!shoot.male_talent || !s.male || s.male.trim().toLowerCase() === shoot.male_talent.trim().toLowerCase()),
        )
        // Stable order — by tab_name then id
        matched.sort((a, b) => a.tab_name.localeCompare(b.tab_name) || a.id - b.id)
        setScripts(matched)
      })
      .finally(() => { if (!cancelled) setScriptsLoading(false) })
    return () => { cancelled = true }
  }, [idToken, shoot.shoot_date, shoot.female_talent, shoot.male_talent, shoot.scenes])

  const [legalDocsLoading, setLegalDocsLoading] = useState(true)

  useEffect(() => {
    if (!idToken) return
    setLegalDocsLoading(true)
    const client = api(idToken)
    client.shoots.legalDocs(shoot.shoot_id)
      .then(r => { setLegalDocs(r); setLegalDocsLoading(false) })
      .catch(() => setLegalDocsLoading(false))
  }, [idToken, shoot.shoot_id])

  useEffect(() => {
    if (!idToken) return
    const shootDate = (shoot.shoot_date || "").slice(0, 10)
    if (!shootDate) return
    const client = api(idToken)
    client.compliance.shoots(shootDate)
      .then(list => {
        const match = list.find(s =>
          s.female_talent.trim().toLowerCase() === (shoot.female_talent || "").trim().toLowerCase(),
        )
        setComplianceShoot(match ?? null)
      })
      .catch(() => setComplianceShoot(null))
  }, [idToken, shoot.shoot_id, shoot.shoot_date, shoot.female_talent])

  const hasScriptContent = useMemo(
    () => scripts.some(s => (s.theme?.trim() || s.plot?.trim())),
    [scripts],
  )

  const primaryStudio = shoot.scenes[0]?.studio ?? ""
  const accent = primaryStudio ? studioColor(primaryStudio) : "var(--color-text-muted)"
  const abbr = primaryStudio ? studioAbbr(primaryStudio) : "—"
  const dateDisplay = formatFullDate(shoot.shoot_date)
  const callSheetHref = `/call-sheets?date=${encodeURIComponent((shoot.shoot_date || "").slice(0, 10))}`
  const scriptsHref = `/scripts?shoot=${encodeURIComponent(shoot.shoot_id)}`
  const complianceHref = `/compliance?date=${encodeURIComponent((shoot.shoot_date || "").slice(0, 10))}`

  let validated = 0
  let total = 0
  for (const sc of shoot.scenes) {
    for (const a of sc.assets) {
      total += 1
      if (a.status === "validated") validated += 1
    }
  }
  const pct = total > 0 ? Math.round((validated / total) * 100) : 0
  const days = Math.floor(shoot.aging_hours / 24)

  if (!mounted) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="shoot-modal-title"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "var(--color-backdrop)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fadeIn var(--duration-base) var(--ease-out-expo) both",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(640px, 100%)",
          maxHeight: "min(85vh, 100dvh - 40px)",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: `1px solid var(--color-border)`,
          boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
          minHeight: 0,
        }}
      >
        {/* Header — pinned so talent name + close stay visible while body scrolls */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--color-border)",
            flexShrink: 0,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: accent,
                marginBottom: 6,
              }}
            >
              {abbr} · {dateDisplay}
            </div>
            <h2
              id="shoot-modal-title"
              style={{
                fontFamily: "var(--font-display-hero)",
                fontWeight: 400,
                fontSize: 28,
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: "var(--color-text)",
                margin: 0,
              }}
            >
              {shoot.female_talent || shoot.shoot_id}
              {shoot.male_talent && (
                <span style={{ color: "var(--color-text-muted)", fontWeight: 500 }}> / {shoot.male_talent}</span>
              )}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              padding: 6,
              background: "transparent",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Body — the only scrolling region; header + footer stay pinned */}
        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 18, overflowY: "auto", flex: "1 1 auto", minHeight: 0 }}>
          {/* Quick-access for director + PA — call sheet and scripts are the
              two docs most often opened mid-shoot. */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: 8,
            }}
          >
            <Link
              href={callSheetHref}
              style={{
                padding: "10px 12px",
                border: "1px solid var(--color-border)",
                background: "var(--color-elevated)",
                color: "var(--color-text)",
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.02em",
                textDecoration: "none",
                display: "flex",
                flexDirection: "column",
                gap: 2,
              }}
            >
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "var(--color-text-faint)",
                }}
              >
                Call Sheet
              </span>
              Open for this date →
            </Link>
            <Link
              href={scriptsHref}
              style={{
                padding: "10px 12px",
                border: "1px solid var(--color-border)",
                background: "var(--color-elevated)",
                color: "var(--color-text)",
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.02em",
                textDecoration: "none",
                display: "flex",
                flexDirection: "column",
                gap: 2,
              }}
            >
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "var(--color-text-faint)",
                }}
              >
                Scripts
              </span>
              Jump to shoot →
            </Link>
          </div>

          {/* Compliance status */}
          <ComplianceRow
            complianceShoot={complianceShoot}
            href={complianceHref}
            shoot={shoot}
          />

          {/* Script(s) — sits right under the two quick-access links so the
              director can skim theme/plot before deciding whether to open the
              full script view. Each card manages its own expand/collapse. */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <SectionLabel>{scripts.length > 1 ? `Scripts · ${scripts.length}` : "Script"}</SectionLabel>
            {scriptsLoading ? (
              <div style={{
                padding: "10px 12px",
                fontSize: 11,
                color: "var(--color-text-faint)",
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
              }}>
                Loading script…
              </div>
            ) : scripts.length === 0 || !hasScriptContent ? (
              <div style={{
                padding: "10px 12px",
                fontSize: 11,
                color: "var(--color-text-faint)",
                background: "var(--color-elevated)",
                border: "1px solid var(--color-border)",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}>
                <FileText size={12} aria-hidden="true" />
                <span>
                  {scripts.length === 0 ? "No script on file for this shoot yet." : "Script placeholder exists — theme and plot are still empty."}
                </span>
                <Link
                  href={scriptsHref}
                  style={{ marginLeft: "auto", color: "var(--color-text-muted)", fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", textDecoration: "none" }}
                >
                  Write →
                </Link>
              </div>
            ) : (
              <div
                id="shoot-modal-script-body"
                style={{ display: "flex", flexDirection: "column", gap: 10 }}
              >
                {scripts.map((s, i) => (
                  <ScriptCard
                    key={s.id}
                    script={s}
                    expanded={expandedIds.has(s.id)}
                    onToggle={() => setExpandedIds(prev => {
                      const next = new Set(prev)
                      if (next.has(s.id)) next.delete(s.id)
                      else next.add(s.id)
                      return next
                    })}
                    accent={studioColor(s.studio)}
                    isLast={i === scripts.length - 1}
                  />
                ))}
              </div>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
            <ModalStat label="Progress" value={`${pct}%`} sub={`${validated}/${total} assets`} />
            <ModalStat label="Aging" value={days > 0 ? `${days}d` : "—"} sub={shoot.aging_hours > 0 ? `${shoot.aging_hours}h total` : "fresh"} />
            <ModalStat label="Scenes" value={String(shoot.scenes.length)} sub={shoot.source_tab || "—"} />
          </div>

          {(shoot.female_talent || shoot.male_talent) && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <SectionLabel>Talent</SectionLabel>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
                {shoot.female_talent && (
                  <TalentRow
                    name={shoot.female_talent}
                    agency={shoot.female_agency}
                    rate={shoot.female_rate}
                    paymentName={shoot.female_payment_name}
                    w9Name={legalDocs?.w9_name}
                    legalFiles={legalDocs?.files}
                    folderUrl={legalDocs?.folder_url ?? undefined}
                    loading={legalDocsLoading}
                  />
                )}
                {shoot.male_talent && (
                  <TalentRow
                    name={shoot.male_talent}
                    agency={shoot.male_agency}
                    rate={shoot.male_rate}
                    paymentName={shoot.male_payment_name}
                    legalFiles={legalDocs?.files}
                    folderUrl={legalDocs?.folder_url ?? undefined}
                    loading={legalDocsLoading}
                  />
                )}
              </div>
            </div>
          )}

          {shoot.scenes.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <SectionLabel>Scenes</SectionLabel>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {shoot.scenes.map((sc, idx) => {
                  let sceneVal = 0
                  let sceneTot = 0
                  for (const a of sc.assets) { sceneTot += 1; if (a.status === "validated") sceneVal += 1 }
                  const scenePct = sceneTot ? Math.round((sceneVal / sceneTot) * 100) : 0
                  const sceneKey = sc.scene_id || `scene-${idx}`
                  const isSceneExpanded = expandedScenes.has(sceneKey)
                  return (
                    <div
                      key={sceneKey}
                      style={{
                        background: "var(--color-elevated)",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setExpandedScenes(prev => {
                          const next = new Set(prev)
                          if (next.has(sceneKey)) next.delete(sceneKey)
                          else next.add(sceneKey)
                          return next
                        })}
                        style={{
                          all: "unset",
                          display: "grid",
                          gridTemplateColumns: "auto 1fr auto auto",
                          gap: 10,
                          alignItems: "center",
                          padding: "8px 10px",
                          width: "100%",
                          boxSizing: "border-box",
                          cursor: "pointer",
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 10,
                            letterSpacing: "0.08em",
                            color: studioColor(sc.studio),
                            fontWeight: 700,
                          }}
                        >
                          {sc.scene_id || sc.scene_type || `#${idx + 1}`}
                        </span>
                        <span style={{ fontSize: 12, color: "var(--color-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {sc.title || sc.scene_type}
                        </span>
                        <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontVariantNumeric: "tabular-nums" }}>
                          {sceneVal}/{sceneTot} · {scenePct}%
                        </span>
                        {isSceneExpanded ? <ChevronUp size={11} aria-hidden="true" /> : <ChevronDown size={11} aria-hidden="true" />}
                      </button>
                      {isSceneExpanded && (
                        <div
                          style={{
                            borderTop: "1px solid var(--color-border)",
                            padding: "8px 10px",
                            display: "grid",
                            gridTemplateColumns: "repeat(2, 1fr)",
                            gap: "4px 12px",
                          }}
                        >
                          {SHOOT_ASSET_ORDER.map(at => {
                            const asset = sc.assets.find(a => a.asset_type === at)
                            const status = asset?.status ?? "not_present"
                            const dotColor =
                              status === "validated" ? "var(--color-ok)"
                              : status === "available" ? "#f59e0b"
                              : status === "stuck" ? "var(--color-err)"
                              : "var(--color-text-faint)"
                            return (
                              <div key={at} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span
                                  aria-hidden="true"
                                  style={{
                                    width: 5, height: 5, borderRadius: "50%", flexShrink: 0,
                                    background: dotColor,
                                  }}
                                />
                                <span style={{ fontSize: 10, color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {SHOOT_ASSET_LABELS[at]}
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer — pinned so Close / Open in Shoots stay reachable regardless of body scroll */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            flexShrink: 0,
            background: "var(--color-surface)",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "transparent",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              cursor: "pointer",
            }}
          >
            Close
          </button>
          <Link
            href="/shoots"
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-lime)",
              color: "var(--color-lime-ink)",
              textDecoration: "none",
              border: "1px solid var(--color-lime)",
            }}
          >
            Open in Shoots →
          </Link>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function ComplianceRow({
  complianceShoot,
  href,
  shoot,
}: {
  complianceShoot: ComplianceShoot | null | undefined
  href: string
  shoot: Shoot
}) {
  const loading = complianceShoot === undefined

  let statusLabel = "Not started"
  let statusColor = "var(--color-text-faint)"
  let statusBg = "rgba(255,255,255,0.04)"
  let statusBorder = "var(--color-border)"

  if (complianceShoot?.is_complete) {
    statusLabel = "Complete"
    statusColor = "var(--color-lime)"
    statusBg = "rgba(190,214,47,0.1)"
    statusBorder = "rgba(190,214,47,0.3)"
  } else if (complianceShoot?.pdfs_ready || (complianceShoot?.photos_uploaded ?? 0) > 0) {
    statusLabel = "In progress"
    statusColor = "#fbbf24"
    statusBg = "rgba(251,191,36,0.08)"
    statusBorder = "rgba(251,191,36,0.25)"
  }

  const ctaLabel = complianceShoot?.is_complete
    ? "View →"
    : complianceShoot?.pdfs_ready || (complianceShoot?.photos_uploaded ?? 0) > 0
      ? "Continue →"
      : "Start →"

  const pdfTalents: { slug: string; label: string }[] = complianceShoot?.pdfs_ready
    ? [
        { slug: shoot.female_talent.replace(/ /g, ""), label: shoot.female_talent },
        ...(shoot.male_talent ? [{ slug: shoot.male_talent.replace(/ /g, ""), label: shoot.male_talent }] : []),
      ]
    : []

  const shootId = complianceShoot?.shoot_id ?? shoot.shoot_id

  return (
    <div>
      <SectionLabel>Compliance</SectionLabel>
      <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 6 }}>
        {/* Status + link row */}
        <Link
          href={href}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 12px",
            border: `1px solid ${statusBorder}`,
            background: statusBg,
            textDecoration: "none",
          }}
        >
          <ClipboardCheck size={14} color={statusColor} aria-hidden="true" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-text)", marginBottom: 1 }}>
              {loading ? "Loading…" : statusLabel}
            </div>
            {!loading && complianceShoot && (
              <div style={{ fontSize: 10, color: "var(--color-text-faint)" }}>
                {complianceShoot.pdfs_ready ? "Docs ready" : "No docs yet"}
                {complianceShoot.photos_uploaded > 0 && ` · ${complianceShoot.photos_uploaded} photo${complianceShoot.photos_uploaded !== 1 ? "s" : ""}`}
              </div>
            )}
          </div>
          <span style={{ fontSize: 11, fontWeight: 700, color: statusColor, whiteSpace: "nowrap" }}>
            {loading ? "" : ctaLabel}
          </span>
        </Link>

        {/* Per-talent PDF view links when docs are ready */}
        {pdfTalents.length > 0 && (
          <div style={{ display: "flex", gap: 6 }}>
            {pdfTalents.map(({ slug, label }) => (
              <a
                key={slug}
                href={`/api/compliance/${encodeURIComponent(shootId)}/pdf?talent=${encodeURIComponent(slug)}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  flex: 1,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                  padding: "8px 10px",
                  background: "var(--color-elevated)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                  fontSize: 11, fontWeight: 700, textDecoration: "none",
                  letterSpacing: "0.04em",
                }}
              >
                <FileText size={12} />
                {label} agreement ↗
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TalentRow({
  name,
  agency,
  rate,
  paymentName,
  w9Name,
  legalFiles,
  folderUrl,
  loading,
}: {
  name: string
  agency?: string
  rate?: string
  paymentName?: string
  w9Name?: string | null
  legalFiles?: LegalDocFile[]
  folderUrl?: string
  loading?: boolean
}) {
  const resolvedPayTo = paymentName || w9Name || null
  const w9Pending = !loading && !resolvedPayTo && !rate
  // Any PDF in the legal folder is the W9 (files aren't always named "w9")
  const w9Files = (legalFiles ?? []).filter(f => f.mime_type === "application/pdf" || /w9/i.test(f.name))
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "baseline" }}>
        <span style={{ color: "var(--color-text)", fontWeight: 600 }}>{name}</span>
        <span style={{ color: "var(--color-text-muted)" }}>{agency || "—"}</span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          columnGap: 12,
          rowGap: 2,
          fontSize: 11,
          color: "var(--color-text-muted)",
        }}
      >
        <span style={{ color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase", fontSize: 9, fontWeight: 700, alignSelf: "center" }}>Rate</span>
        <span style={{ color: rate ? "var(--color-text)" : "var(--color-text-faint)", fontVariantNumeric: "tabular-nums" }}>
          {rate || (loading ? "…" : w9Pending ? "Not on file" : "—")}
        </span>
        <span style={{ color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase", fontSize: 9, fontWeight: 700, alignSelf: "center" }}>Pay&nbsp;to</span>
        <span style={{ color: resolvedPayTo ? "var(--color-text)" : "var(--color-text-faint)" }}>
          {resolvedPayTo || (loading ? "…" : w9Pending ? "No W9 on file" : "—")}
        </span>
        {(w9Files.length > 0 || folderUrl) && (
          <>
            <span style={{ color: "var(--color-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase", fontSize: 9, fontWeight: 700, alignSelf: "center" }}>W9</span>
            <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {w9Files.length > 0 ? w9Files.map(f => (
                <a
                  key={f.web_view_link}
                  href={f.web_view_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 10, color: "var(--color-lime)", fontWeight: 700, letterSpacing: "0.06em", textDecoration: "none" }}
                >
                  {f.name} ↗
                </a>
              )) : folderUrl ? (
                <a
                  href={folderUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 10, color: "var(--color-text-muted)", fontWeight: 600, textDecoration: "none" }}
                >
                  View folder ↗
                </a>
              ) : null}
            </span>
          </>
        )}
      </div>
    </div>
  )
}

function ModalStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--color-text-faint)" }}>
        {label}
      </div>
      <div
        style={{
          marginTop: 4,
          fontFamily: "var(--font-display-hero)",
          fontWeight: 400,
          fontSize: 22,
          letterSpacing: "-0.02em",
          color: "var(--color-text)",
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function ScriptCard({
  script,
  expanded,
  onToggle,
  accent,
  isLast: _isLast,
}: {
  script: Script
  expanded: boolean
  onToggle: () => void
  accent: string
  isLast: boolean
}) {
  const teaser = (script.theme?.trim() || script.plot?.trim() || "").slice(0, 180)
  const hasDetail =
    (script.theme?.trim() || "") !== "" ||
    (script.plot?.trim() || "") !== "" ||
    (script.wardrobe_f?.trim() || "") !== "" ||
    (script.wardrobe_m?.trim() || "") !== ""
  const cardId = `script-card-${script.id}`
  return (
    <div
      style={{
        background: "var(--color-elevated)",
        border: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header row is a button when the card has content to expand, a plain
          row otherwise — keeps the hit target a single element. */}
      <button
        type="button"
        onClick={hasDetail ? onToggle : undefined}
        aria-expanded={hasDetail ? expanded : undefined}
        aria-controls={hasDetail ? cardId : undefined}
        disabled={!hasDetail}
        style={{
          all: "unset",
          padding: "10px 12px",
          display: "grid",
          gridTemplateColumns: "1fr auto",
          alignItems: "center",
          columnGap: 12,
          cursor: hasDetail ? "pointer" : "default",
          boxSizing: "border-box",
          width: "100%",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                fontWeight: 700,
                color: accent,
              }}
            >
              {script.tab_name}
            </span>
            {script.title && (
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", letterSpacing: "-0.01em" }}>
                {script.title}
              </span>
            )}
          </div>
          {!expanded && teaser && (
            <div
              style={{
                fontSize: 12,
                lineHeight: 1.55,
                color: "var(--color-text-muted)",
                display: "-webkit-box",
                WebkitBoxOrient: "vertical",
                WebkitLineClamp: 2,
                overflow: "hidden",
              }}
            >
              {teaser}
              {teaser.length >= 180 && "…"}
            </div>
          )}
        </div>
        {hasDetail && (
          <span
            aria-hidden="true"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              whiteSpace: "nowrap",
            }}
          >
            {expanded ? "Collapse" : "Expand"}
            {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </span>
        )}
      </button>
      {expanded && hasDetail && (
        <div
          id={cardId}
          style={{
            padding: "4px 12px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            borderTop: "1px solid var(--color-border)",
          }}
        >
          {script.theme?.trim() && (
            <ScriptField label="Theme" value={script.theme} />
          )}
          {script.plot?.trim() && (
            <ScriptField label="Plot" value={script.plot} />
          )}
          {(script.wardrobe_f?.trim() || script.wardrobe_m?.trim()) && (
            <div style={{ display: "grid", gridTemplateColumns: script.wardrobe_f && script.wardrobe_m ? "1fr 1fr" : "1fr", gap: 10 }}>
              {script.wardrobe_f?.trim() && (
                <ScriptField label="Wardrobe · F" value={script.wardrobe_f} />
              )}
              {script.wardrobe_m?.trim() && (
                <ScriptField label="Wardrobe · M" value={script.wardrobe_m} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ScriptField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: "var(--color-text-faint)",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--color-text)", whiteSpace: "pre-wrap" }}>
        {value}
      </div>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--color-text-faint)",
      }}
    >
      {children}
    </div>
  )
}

function normalizeDate(raw: string): string {
  if (!raw) return ""
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10)
  const parts = raw.split("/")
  if (parts.length === 3) {
    const [m, d, y] = parts
    // Handle 2-digit year (e.g. "4/22/26" from Google Sheets) — assume 2000s
    const fullYear = y.length === 2 ? `20${y}` : y
    return `${fullYear}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`
  }
  return raw
}

function formatFullDate(raw: string): string {
  const t = Date.parse(raw)
  if (!Number.isFinite(t)) return raw || "—"
  return new Date(t).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}
