"use client"

import { Panel } from "@/components/ui/panel"

// --- primitives ---------------------------------------------------------

function Mono({ children }: { children: React.ReactNode }) {
  return (
    <code
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: "0.85em",
        color: "var(--color-text)",
        background: "var(--color-elevated)",
        padding: "1px 5px",
        border: "1px solid var(--color-border-subtle)",
      }}
    >
      {children}
    </code>
  )
}

function Tag({ variant, children }: {
  variant: "critical" | "warning" | "good" | "info" | "accent"
  children: React.ReactNode
}) {
  const palette: Record<string, string> = {
    critical: "var(--color-err)",
    warning:  "var(--color-warn)",
    good:     "var(--color-ok)",
    info:     "var(--color-text-faint)",
    accent:   "var(--color-lime)",
  }
  const c = palette[variant]
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 9,
        fontWeight: 700,
        padding: "3px 9px",
        marginBottom: 8,
        textTransform: "uppercase",
        letterSpacing: "0.1em",
        border: `1px solid ${c}`,
        color: c,
      }}
    >
      {children}
    </span>
  )
}

function ScoreBar({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 500, color: "var(--color-text-faint)", marginBottom: 4 }}>
        <span>{label}</span>
        <span style={{ color, fontFamily: "var(--font-mono)" }}>{score}/10</span>
      </div>
      <div style={{ height: 4, background: "var(--color-elevated)", overflow: "hidden", marginBottom: 12 }}>
        <div style={{ height: "100%", width: `${score * 10}%`, background: color }} />
      </div>
    </div>
  )
}

function FindingGrid({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      {children}
    </div>
  )
}

function FindingBox({ title, tag, tagVariant, urgent, children }: {
  title: string
  tag: string
  tagVariant: "critical" | "warning" | "good" | "info" | "accent"
  urgent?: boolean
  children: React.ReactNode
}) {
  const urgentBorder = tagVariant === "critical"
    ? "color-mix(in srgb, var(--color-err) 35%, transparent)"
    : "color-mix(in srgb, var(--color-warn) 35%, transparent)"
  return (
    <div
      style={{
        background: "var(--color-elevated)",
        border: `1px solid ${urgent ? urgentBorder : "var(--color-border)"}`,
        padding: 18,
      }}
    >
      <Tag variant={tagVariant}>{tag}</Tag>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--color-text)",
          letterSpacing: "-0.01em",
          marginBottom: 5,
        }}
      >
        {title}
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.65, color: "var(--color-text-faint)" }}>
        {children}
      </div>
    </div>
  )
}

function ImpactChip({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 8,
        fontWeight: 800,
        padding: "2px 6px",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        marginLeft: 6,
        border: `1px solid ${color}`,
        color,
        position: "relative",
        top: -1,
      }}
    >
      {children}
    </span>
  )
}

// --- sections -----------------------------------------------------------

function OverviewSection() {
  return (
    <Panel title="Overview & Score" variant="label">
      <div style={{ padding: 20 }}>
        <div style={{ fontSize: 12, color: "var(--color-text-faint)", marginBottom: 16, lineHeight: 1.6 }}>
          A Next.js App Router application deployed on Vercel, managing production workflows across 4 studios
          (FuckPassVR, VRHush, VRAllure, NaughtyJOI). Features: shoot scheduling with Gantt-style calendars,
          AI script generation (Ollama + Claude), asset QA tracking (MEGA integration), description generation,
          title card creation, compilations, and ticketing. Auth via Google OAuth with RBAC. Backed by a
          Python/Streamlit API on a Windows server.
        </div>
        <div
          style={{
            background: "var(--color-elevated)",
            border: "1px solid var(--color-border)",
            padding: 20,
          }}
        >
          <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
            {/* Conic score dial */}
            <div
              style={{
                width: 90,
                height: 90,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                background: "conic-gradient(var(--color-lime) 0deg, var(--color-lime) 252deg, var(--color-border) 252deg)",
                borderRadius: "50%",
              }}
            >
              <div
                style={{
                  width: 68,
                  height: 68,
                  borderRadius: "50%",
                  background: "var(--color-elevated)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 22,
                  fontWeight: 800,
                  color: "var(--color-lime)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                7.0
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginBottom: 12, lineHeight: 1.5 }}>
                Strong engineering with a well-executed design system. Main gaps are in content density and the
                v1→v2 transition overhead.
              </div>
              <ScoreBar label="Design System & Tokens"      score={9} color="var(--color-lime)" />
              <ScoreBar label="Component Architecture"      score={8} color="var(--color-ok)"   />
              <ScoreBar label="Error Handling"              score={8} color="var(--color-ok)"   />
              <ScoreBar label="Responsive / Mobile"         score={7} color="var(--color-ok)"   />
              <ScoreBar label="Dashboard Content Density"   score={5} color="var(--color-warn)" />
              <ScoreBar label="Code Complexity"             score={5} color="var(--color-warn)" />
            </div>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function DesignSystemSection() {
  const tokens = [
    { name: "base",      value: "oklch(7% 0.005 82)",   color: "oklch(7% 0.005 82)"   },
    { name: "surface",   value: "oklch(11% 0.005 82)",  color: "oklch(11% 0.005 82)"  },
    { name: "elevated",  value: "oklch(15% 0.008 82)",  color: "oklch(15% 0.008 82)"  },
    { name: "border",    value: "oklch(20% 0.006 82)",  color: "oklch(20% 0.006 82)"  },
    { name: "lime (CTA)", value: "#bed62f",             color: "#bed62f"               },
    { name: "ok",        value: "#22c55e",              color: "#22c55e"               },
    { name: "warn",      value: "#eab308",              color: "#eab308"               },
    { name: "err",       value: "#ef4444",              color: "#ef4444"               },
    { name: "fpvr",      value: "#f97316",              color: "#f97316"               },
    { name: "vrh",       value: "#8b5cf6",              color: "#8b5cf6"               },
    { name: "vra",       value: "#ec4899",              color: "#ec4899"               },
    { name: "njoi",      value: "#3b82f6",              color: "#3b82f6"               },
  ]

  return (
    <Panel title="Design System" variant="label">
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        <FindingGrid>
          <FindingBox title="oklch Color Architecture" tag="Excellent" tagVariant="good">
            All surfaces use oklch with consistent hue (82° lime warmth), chroma, and lightness steps.
            Semantic aliases (<Mono>--color-cta</Mono>, <Mono>--color-nav-active</Mono>) separate intent from raw color.
            Studio brand colors are distinct and well-spaced on the wheel.
          </FindingBox>
          <FindingBox title="Typography Stack" tag="Excellent" tagVariant="good">
            <strong>Geist</strong> (body), <strong>General Sans</strong> (display headings),{" "}
            <strong>Anton</strong> (hero display — "film-slate grotesque"), <strong>Geist Mono</strong> (data).
            Four faces with clear hierarchy roles. The type scale has 8 steps from 11px captions to clamp() display.
          </FindingBox>
          <FindingBox title="v2 Feature Flag System" tag="Strong" tagVariant="good">
            <Mono>data-eclatech="v2"</Mono> on &lt;html&gt; gates an entire parallel design language —
            ec-block, ec-strip, ec-cal, ec-pill, ec-btn variants. Clean progressive rollout with zero impact
            when flag is off. Dead-code eliminated in production builds.
          </FindingBox>
          <FindingBox title="Motion & Accessibility" tag="Strong" tagVariant="good">
            Custom easing tokens (ease-out-quart, ease-out-expo), duration scale (fast/base/slow), button
            press feedback (scale 0.97), <Mono>prefers-reduced-motion</Mono> support, focus-visible rings with
            box-shadow fallback, WCAG AA text contrast (documented via TKT-0109).
          </FindingBox>
        </FindingGrid>

        {/* Color token table */}
        <div style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", padding: 16 }}>
          <div
            style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--color-text-faint)",
              marginBottom: 10,
            }}
          >
            Color Tokens
          </div>
          {tokens.map(t => (
            <div
              key={t.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "5px 0",
                borderBottom: "1px solid var(--color-border-subtle)",
              }}
            >
              <div
                style={{
                  width: 20,
                  height: 20,
                  flexShrink: 0,
                  border: "1px solid var(--color-border)",
                  background: t.color,
                }}
              />
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--color-text-faint)",
                  width: 90,
                }}
              >
                {t.name}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--color-text)",
                }}
              >
                {t.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function StrengthsSection() {
  return (
    <Panel title="Strengths" variant="label">
      <div style={{ padding: 20 }}>
        <FindingGrid>
          <FindingBox title="Clean Component Hierarchy" tag="Architecture" tagVariant="good">
            32 UI components (command palette, modals, calendars, skeleton loaders, toast, studio badges) plus
            4 layout components (app-shell, sidebar, topbar, mobile-nav). Each page has a dedicated client
            component + thin server page.tsx. Well-decomposed.
          </FindingBox>
          <FindingBox title="Proper Error Boundaries" tag="Error Handling" tagVariant="good">
            <Mono>lib/errors.ts</Mono> maps HTTP status codes to human-readable messages. 401 → "Session
            expired — refresh the page". Network failures → "Can't reach the server". No raw API payloads
            leak to UI. Retry-error and error-alert components for consistent display.
          </FindingBox>
          <FindingBox title="Mock Mode for Offline Dev" tag="Dev Experience" tagVariant="good">
            <Mono>npm run dev:mock</Mono> bypasses Google OAuth and serves fixtures from{" "}
            <Mono>dev-fixtures.ts</Mono> (30KB of realistic data). Picsum.photos for thumbnails. Verified
            dead-code-eliminated in production. Enables visual verification without a live backend.
          </FindingBox>
          <FindingBox title="Smart Briefing Engine" tag="Dashboard" tagVariant="good">
            Dashboard computes a priority briefing: stuck shoots (72h+) → missing assets (10+) → queued
            scripts → "All clear". Tone ramps by magnitude via <Mono>toneForCount()</Mono>. Failed fetches
            show "Can't reach server" instead of false "all clear". Thoughtful degradation.
          </FindingBox>
          <FindingBox title="Responsive Sidebar + Command Palette" tag="Navigation" tagVariant="good">
            3-tier sidebar: full labels (xl+), icon + short label (lg), hidden with bottom nav (mobile). ⌘K
            command palette (8KB component) for power users. RBAC filters nav items per user's allowed tabs.
            Live clock in sidebar rail — production-studio touch.
          </FindingBox>
          <FindingBox title="Promise.allSettled for Resilience" tag="Data Loading" tagVariant="good">
            Dashboard loads 7+ data sources in parallel via <Mono>Promise.allSettled</Mono>. Each source can
            fail independently without blocking others. Partial data renders normally; only the failed section
            shows an error state.
          </FindingBox>
        </FindingGrid>
      </div>
    </Panel>
  )
}

function ArchSection() {
  const archStyle = { fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: "2", color: "var(--color-text-faint)" }

  const AFile = ({ children }: { children: React.ReactNode }) => (
    <span style={{ color: "var(--color-text)" }}>{children}</span>
  )
  const ADim = ({ children }: { children: React.ReactNode }) => (
    <span style={{ color: "var(--color-text-faint)", opacity: 0.7 }}>{children}</span>
  )

  return (
    <Panel title="Architecture" variant="label">
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* File tree */}
        <div style={{ background: "var(--color-elevated)", border: "1px solid var(--color-border)", padding: 20 }}>
          <div style={archStyle}>
            <div>
              <span style={{ color: "var(--color-lime)", fontWeight: 700 }}>hub/</span>{" "}
              <ADim>— Next.js App Router on Vercel</ADim>
            </div>
            <div style={{ paddingLeft: 16 }}>
              <div><AFile>├── app/layout.tsx</AFile> <ADim>— Geist + General Sans + Anton fonts, v2 flag</ADim></div>
              <div><AFile>├── app/globals.css</AFile> <ADim>— Tailwind v4 + oklch tokens + v2 primitives</ADim></div>
              <div><AFile>├── app/(app)/dashboard/</AFile> <ADim>— briefing engine, triage feed, notifications</ADim></div>
              <div><AFile>├── app/(app)/shoots/</AFile> <ADim>— shoot-board (1,609 lines), Gantt calendar, modals</ADim></div>
              <div><AFile>├── app/(app)/scripts/</AFile> <ADim>— generator (1,013 lines) + batch panel (633 lines)</ADim></div>
              <div><AFile>├── app/(app)/missing/</AFile> <ADim>— scene grid (821 lines) + detail (899 lines), view transitions</ADim></div>
              <div><AFile>├── app/(app)/descriptions/</AFile> <ADim>— desc generator (1,268 lines)</ADim></div>
              <div><AFile>├── app/(app)/research/</AFile> <ADim>— model search (1,115 lines)</ADim></div>
              <div><AFile>├── app/(app)/compilations/</AFile> <ADim>— comp builder (879 lines)</ADim></div>
              <div><AFile>├── app/(app)/tickets/</AFile> <ADim>— ticket list (1,306 lines) + detail modal</ADim></div>
              <div><AFile>├── app/(app)/admin/</AFile> <ADim>— users, prompts, sync, audit, tasks</ADim></div>
              <div><AFile>├── components/ui/</AFile> <ADim>— 26 components (modals, calendar, toast, skeleton…)</ADim></div>
              <div><AFile>├── components/layout/</AFile> <ADim>— sidebar, topbar, mobile-nav, app-shell</ADim></div>
              <div><AFile>├── lib/api.ts</AFile> <ADim>— API client + types, proxy to Python backend</ADim></div>
              <div><AFile>├── lib/dev-mock-api.ts</AFile> <ADim>— mock API for offline dev</ADim></div>
              <div><AFile>├── lib/errors.ts</AFile> <ADim>— HTTP status → human-readable messages</ADim></div>
              <div><AFile>├── lib/rbac.ts</AFile> <ADim>— role-based access control</ADim></div>
              <div><AFile>└── auth.ts</AFile> <ADim>— Google OAuth, session management</ADim></div>
            </div>
            <div
              style={{
                marginTop: 12,
                paddingTop: 10,
                borderTop: "1px solid var(--color-border)",
              }}
            >
              <span style={{ color: "var(--color-lime)" }}>Backend:</span>{" "}
              <ADim>Python API on Windows (NSSM) → Google Sheets + MEGA + Ollama + Claude + fal.ai</ADim>
            </div>
          </div>
        </div>

        <FindingGrid>
          <FindingBox title="5+ Files Over 1,000 Lines" tag="Observation" tagVariant="info">
            shoot-board (1,609), ticket-list (1,306), approval-list (1,275), desc-generator (1,268), and
            model-search (1,115) are the top megacomponents. Each should be split into sub-components,
            hooks, and utilities.
          </FindingBox>
          <FindingBox title="View Transitions for Scene Navigation" tag="Strong" tagVariant="good">
            The missing/scene pages use CSS View Transitions API (<Mono>view-transition-name: scene-frame-*</Mono>)
            for card→detail morphing. 280ms with ease-out-expo. Graceful fallback via{" "}
            <Mono>prefers-reduced-motion</Mono>.
          </FindingBox>
        </FindingGrid>
      </div>
    </Panel>
  )
}

function IssuesSection() {
  return (
    <Panel title="Issues & Friction" variant="label">
      <div style={{ padding: 20 }}>
        <FindingGrid>
          <FindingBox title="Massive Client Components" tag="Complexity" tagVariant="critical" urgent>
            <Mono>shoot-board.tsx</Mono> (1,609 lines), <Mono>approval-list.tsx</Mono> (1,275),{" "}
            <Mono>desc-generator.tsx</Mono> (1,268), <Mono>model-search.tsx</Mono> (1,115),{" "}
            <Mono>script-generator.tsx</Mono> (1,013). Single-file megacomponents that are hard to test,
            review, and maintain.
          </FindingBox>
          <FindingBox title="Parallel Design Systems in One CSS File" tag="v1/v2 Divergence" tagVariant="critical" urgent>
            <Mono>globals.css</Mono> carries both v1 and v2 styles gated behind{" "}
            <Mono>[data-eclatech="v2"]</Mono>. Both versions ship to every user. When v2 is fully adopted,
            all v1 CSS becomes dead weight. Needs a migration + cleanup plan.
          </FindingBox>
          <FindingBox title="Empty States Lack Guidance" tag="Dashboard" tagVariant="warning" urgent>
            When the API is unreachable, the briefing shows "Can't reach the production server" — good
            messaging, but the rest of the page shows empty sections with no CTAs or skeleton content. The
            dashboard becomes a dead-end instead of offering offline-capable actions.
          </FindingBox>
          <FindingBox title="Month Calendar Component Size" tag="Calendar" tagVariant="warning" urgent>
            <Mono>month-calendar.tsx</Mono> is 580 lines and <Mono>shoot-modal.tsx</Mono> is 835 lines.
            The calendar likely reimplements date logic that could use a lightweight library. The shoot modal
            handles creation, editing, and all form states in one file.
          </FindingBox>
          <FindingBox title="Bottom Nav Truncation" tag="Mobile" tagVariant="warning" urgent>
            Mobile bottom nav shows Home, Shoots, Calls, Scripts, and a "More" overflow. Key modules like
            Grail Assets and Tickets are buried. The hierarchy may not match actual usage frequency — needs
            analytics to validate.
          </FindingBox>
          <FindingBox title="Monolith API Client" tag="API Layer" tagVariant="warning" urgent>
            <Mono>lib/api.ts</Mono> handles auth proxy, all endpoint types, response parsing, and type
            definitions in one file. Consider splitting into per-domain modules (shoots, scripts, scenes,
            notifications).
          </FindingBox>
        </FindingGrid>
      </div>
    </Panel>
  )
}

function RecsSection() {
  const recs = [
    {
      title: "Decompose Megacomponents",
      desc: (
        <>
          Split the 5 files over 1,000 lines (shoot-board, approval-list, desc-generator, model-search,
          script-generator) into sub-components. Extract form logic into hooks, modals into standalone files,
          and table renderers into reusable pieces.
        </>
      ),
      impact: "High",
      color: "var(--color-err)",
    },
    {
      title: "Plan v1→v2 Migration",
      desc: (
        <>
          <Mono>globals.css</Mono> ships both v1 and v2 styles. Define a timeline to migrate remaining v1
          pages to v2 primitives, then purge the v1 CSS. Consider splitting into{" "}
          <Mono>base.css</Mono> + <Mono>v2.css</Mono> with conditional imports.
        </>
      ),
      impact: "High",
      color: "var(--color-err)",
    },
    {
      title: "Split lib/api.ts",
      desc: (
        <>
          The API client handles every endpoint type. Split into domain modules:{" "}
          <Mono>shoots.ts</Mono>, <Mono>scripts.ts</Mono>, <Mono>scenes.ts</Mono>,{" "}
          <Mono>notifications.ts</Mono>. Keeps type co-location and makes tree-shaking possible per route.
        </>
      ),
      impact: "Medium",
      color: "var(--color-warn)",
    },
    {
      title: "Dashboard Offline Fallback",
      desc: (
        <>
          When the API is unreachable, dashboard sections are empty. Cache the last successful briefing in{" "}
          <Mono>localStorage</Mono> and display it with a "stale data" badge. Add offline-capable quick
          actions (open recently viewed, jump to bookmarked scenes).
        </>
      ),
      impact: "Medium",
      color: "var(--color-warn)",
    },
    {
      title: "Mobile Nav Analytics",
      desc: (
        <>
          The bottom nav shows Home/Shoots/Calls/Scripts/More. Run usage analytics to verify these are the
          top 4 modules on mobile. Grail Assets (Missing) may be higher-traffic than Call Sheets for editors.
        </>
      ),
      impact: "Medium",
      color: "var(--color-warn)",
    },
    {
      title: "Extract Calendar Logic",
      desc: (
        <>
          <Mono>month-calendar.tsx</Mono> (580 lines) likely reimplements date math. Consider{" "}
          <Mono>date-fns</Mono> or the Temporal API for date operations. Extract the calendar grid renderer
          from shoot-specific event logic.
        </>
      ),
      impact: "Low",
      color: "var(--color-ok)",
    },
    {
      title: "Component Documentation",
      desc: (
        <>
          The v2 design system (ec-block, ec-strip, ec-cal, ec-pill, ec-btn, ec-seg, ec-row) is well-built
          but exists only in CSS comments. A Storybook or simple catalog page would help onboard contributors.
        </>
      ),
      impact: "Low",
      color: "var(--color-ok)",
    },
  ]

  return (
    <Panel title="Recommendations" variant="label">
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 8 }}>
        {recs.map((r, i) => (
          <div
            key={i}
            style={{
              background: "var(--color-elevated)",
              border: "1px solid var(--color-border)",
              padding: 16,
              display: "flex",
              gap: 12,
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                width: 24,
                height: 24,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 800,
                flexShrink: 0,
                fontFamily: "var(--font-mono)",
                border: `1px solid ${r.color}`,
                color: r.color,
              }}
            >
              {i + 1}
            </div>
            <div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--color-text)",
                  marginBottom: 3,
                  letterSpacing: "-0.01em",
                }}
              >
                {r.title}
                <ImpactChip color={r.color}>{r.impact}</ImpactChip>
              </div>
              <div style={{ fontSize: 11, lineHeight: 1.6, color: "var(--color-text-faint)" }}>
                {r.desc}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

// --- main export --------------------------------------------------------

export function AnalysisPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Subtitle */}
      <div style={{ fontSize: 11, color: "var(--color-text-faint)", fontStyle: "italic" }}>
        Code-level review — Next.js App Router, Tailwind v4, oklch tokens, v2 design system
      </div>

      <OverviewSection />
      <DesignSystemSection />
      <StrengthsSection />
      <ArchSection />
      <IssuesSection />
      <RecsSection />
    </div>
  )
}
