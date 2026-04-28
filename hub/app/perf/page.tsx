import { auth } from "@/auth"

/**
 * Authenticated A/B benchmark — prod backend vs staging backend.
 *
 * Visit /perf while signed in. The server-side render:
 *   1. Pulls your idToken from the next-auth session
 *   2. Hits a curated set of dashboard-pattern endpoints against both
 *      backends, with the SAME bearer token
 *   3. Renders a min/p50/max table + delta column
 *
 * Both URLs are reachable from your Mac via Tailscale (prod via public
 * Funnel on :443, staging via tailnet on :10000), so the network base
 * is comparable. The point is to surface the *server-side* gains: token
 * cache, scene_stats_cache, budgets-from-SQLite, /scenes/recent collapse.
 *
 * This page is intentionally NOT linked from anywhere — it's a one-shot
 * measurement tool. Delete the route after we've confirmed the numbers.
 */

const PROD_URL = "https://desktop-9d407v9.tail3f755a.ts.net"
const STG_URL  = "https://desktop-9d407v9.tail3f755a.ts.net:10000"

interface Sample { status: number; ms: number }
interface Bench {
  base: string
  path: string
  reps: number
  samples: Sample[]
  min: number
  p50: number
  max: number
  okCount: number
}

// Wide enough to cover the dashboard's typical six-call burst plus a few
// representative non-dashboard endpoints. Each rep is sequential per side
// so we measure repeat-call behaviour (where the token cache matters);
// the two sides run sequentially so we don't fight each other for tailnet.
const ENDPOINTS: { path: string; reps: number; note?: string }[] = [
  { path: "/api/scenes/stats",                                                                                  reps: 6, note: "uses scene_stats_cache on staging" },
  { path: "/api/notifications/?limit=12",                                                                       reps: 6 },
  { path: "/api/scripts/?needs_script=true",                                                                    reps: 6 },
  { path: "/api/shoots/",                                                                                       reps: 3, note: "heaviest — Drive + Budgets" },
  { path: "/api/scenes/?studio=VRHush&limit=5&missing_only=true",                                               reps: 6, note: "old per-studio pattern" },
  { path: "/api/scenes/recent?studios=FuckPassVR,VRHush,VRAllure&per_studio=5&missing_only=true",               reps: 6, note: "new bulk endpoint (staging only)" },
  { path: "/api/health",                                                                                        reps: 6 },
]

async function timed(url: string, token: string, signal: AbortSignal): Promise<Sample> {
  const t0 = Date.now()
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal,
    })
    // Drain the body so we measure full transfer, not just header arrival.
    await res.text()
    return { status: res.status, ms: Date.now() - t0 }
  } catch {
    return { status: 0, ms: Date.now() - t0 }
  }
}

async function runBench(base: string, path: string, reps: number, token: string): Promise<Bench> {
  const samples: Sample[] = []
  for (let i = 0; i < reps; i++) {
    const ctrl = new AbortController()
    const to = setTimeout(() => ctrl.abort(), 30_000)
    try {
      samples.push(await timed(base + path, token, ctrl.signal))
    } finally {
      clearTimeout(to)
    }
  }
  const okSamples = samples.filter(s => s.status === 200)
  const times = (okSamples.length ? okSamples : samples).map(s => s.ms).sort((a, b) => a - b)
  return {
    base, path, reps,
    samples,
    min: times[0] ?? 0,
    p50: times[Math.floor(times.length / 2)] ?? 0,
    max: times[times.length - 1] ?? 0,
    okCount: okSamples.length,
  }
}

function fmt(n: number): string {
  return `${n}ms`
}

function deltaFmt(prod: number, stg: number): { text: string; color: string } {
  if (!prod || !stg) return { text: "—", color: "var(--color-text-muted)" }
  const diff = prod - stg
  const pct = ((diff / prod) * 100).toFixed(0)
  if (Math.abs(diff) < 5) return { text: "≈ same", color: "var(--color-text-muted)" }
  if (diff > 0)  return { text: `↓ ${diff}ms (-${pct}%)`,        color: "var(--color-ok, #4ade80)" }
  return                { text: `↑ ${-diff}ms (+${-Number(pct)}%)`, color: "var(--color-warn, #f97316)" }
}

export const dynamic = "force-dynamic"

export default async function PerfPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken

  if (!idToken) {
    return (
      <main style={{ padding: 32, fontFamily: "monospace" }}>
        <h1>Perf Benchmark</h1>
        <p>Not signed in — visit <code>/login</code> first.</p>
      </main>
    )
  }

  const results: { path: string; note?: string; prod: Bench; stg: Bench }[] = []
  for (const e of ENDPOINTS) {
    const prod = await runBench(PROD_URL, e.path, e.reps, idToken)
    const stg  = await runBench(STG_URL,  e.path, e.reps, idToken)
    results.push({ path: e.path, note: e.note, prod, stg })
  }

  // Aggregate — what would a "typical dashboard render" look like in total?
  // The dashboard issues these 6 endpoints (plus health) in parallel via
  // <Suspense>. Sequential sum is a worst-case ceiling; it mostly tells you
  // which endpoint dominates. p50 sum is a realistic-ish "if the slowest
  // dictates" number.
  const dashPaths = [
    "/api/scenes/stats",
    "/api/notifications/?limit=12",
    "/api/scripts/?needs_script=true",
    "/api/shoots/",
  ]
  const dashFanOut = "/api/scenes/?studio=VRHush&limit=5&missing_only=true" // prod's per-studio shape
  const dashBulk   = "/api/scenes/recent?studios=FuckPassVR,VRHush,VRAllure&per_studio=5&missing_only=true"

  const sum = (paths: string[], side: "prod" | "stg") =>
    paths.reduce((acc, p) => acc + (results.find(r => r.path === p)?.[side].p50 ?? 0), 0)

  const prodDashSum = sum(dashPaths, "prod") + 3 * (results.find(r => r.path === dashFanOut)?.prod.p50 ?? 0)
  const stgDashSum  = sum(dashPaths, "stg")  + 1 * (results.find(r => r.path === dashBulk)?.stg.p50 ?? 0)

  return (
    <main style={{ padding: 32, fontFamily: "var(--font-mono, monospace)", maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Perf Benchmark — prod vs staging</h1>
      <p style={{ color: "var(--color-text-muted)", marginBottom: 24 }}>
        Both backends hit from this server with the same Google ID token.
        Prod = <code>{PROD_URL}</code>. Staging = <code>{STG_URL}</code>.
      </p>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--color-border, #333)", textAlign: "left" }}>
            <th style={{ padding: "8px 6px" }}>Endpoint</th>
            <th style={{ padding: "8px 6px" }}>Reps</th>
            <th style={{ padding: "8px 6px" }}>Prod min/p50/max</th>
            <th style={{ padding: "8px 6px" }}>Stg min/p50/max</th>
            <th style={{ padding: "8px 6px" }}>Δ p50</th>
          </tr>
        </thead>
        <tbody>
          {results.map(r => {
            const d = deltaFmt(r.prod.p50, r.stg.p50)
            return (
              <tr key={r.path} style={{ borderBottom: "1px solid var(--color-border-subtle, #222)" }}>
                <td style={{ padding: "8px 6px" }}>
                  <code style={{ fontSize: 12 }}>{r.path}</code>
                  {r.note && (
                    <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>{r.note}</div>
                  )}
                </td>
                <td style={{ padding: "8px 6px" }}>{r.prod.reps}</td>
                <td style={{ padding: "8px 6px" }}>
                  {fmt(r.prod.min)} / <strong>{fmt(r.prod.p50)}</strong> / {fmt(r.prod.max)}
                  {r.prod.okCount < r.prod.reps && (
                    <span style={{ color: "var(--color-warn, #f97316)" }}>
                      {" "}({r.prod.okCount}/{r.prod.reps} ok)
                    </span>
                  )}
                </td>
                <td style={{ padding: "8px 6px" }}>
                  {fmt(r.stg.min)} / <strong>{fmt(r.stg.p50)}</strong> / {fmt(r.stg.max)}
                  {r.stg.okCount < r.stg.reps && (
                    <span style={{ color: "var(--color-warn, #f97316)" }}>
                      {" "}({r.stg.okCount}/{r.stg.reps} ok)
                    </span>
                  )}
                </td>
                <td style={{ padding: "8px 6px", color: d.color }}>{d.text}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <h2 style={{ fontSize: 18, marginTop: 32, marginBottom: 8 }}>Dashboard total (sum of p50)</h2>
      <p style={{ color: "var(--color-text-muted)", fontSize: 12, marginBottom: 12 }}>
        Sequential ceiling — actual dashboard parallelizes via Suspense, but the slowest call
        dictates real-world TTFB. Includes 3× per-studio scene-list calls on prod (the old
        fan-out) vs 1 bulk <code>/scenes/recent</code> call on staging.
      </p>
      <table style={{ borderCollapse: "collapse", fontSize: 14 }}>
        <tbody>
          <tr><td style={{ padding: 4, paddingRight: 24 }}>Prod sum:</td><td><strong>{fmt(prodDashSum)}</strong></td></tr>
          <tr><td style={{ padding: 4, paddingRight: 24 }}>Stg sum:</td><td><strong>{fmt(stgDashSum)}</strong></td></tr>
          <tr><td style={{ padding: 4, paddingRight: 24 }}>Δ:</td><td style={{ color: deltaFmt(prodDashSum, stgDashSum).color }}><strong>{deltaFmt(prodDashSum, stgDashSum).text}</strong></td></tr>
        </tbody>
      </table>

      <p style={{ marginTop: 32, fontSize: 11, color: "var(--color-text-muted)" }}>
        Reload to re-run. Token cache on staging means a second run within 60s
        of the first should be measurably faster than the cold sample. The
        dashboard total assumes parallel-render and doesn&apos;t account for
        Vercel <code>unstable_cache</code> (which only kicks in on production
        builds, not <code>npm run dev</code>).
      </p>
    </main>
  )
}
