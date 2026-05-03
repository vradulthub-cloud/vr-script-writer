import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { api, type Script } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import type { Briefing } from "@/components/ui/today-briefing"
import { parseLocalDate } from "@/lib/dates"

const ScriptGenerator = nextDynamic(() => import("./script-generator").then(m => m.ScriptGenerator))

export const dynamic = "force-dynamic"

export default async function ScriptsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  const userProfile = await requireTab("Scripts", idToken)
  const client = api(session)

  // Parallelize: tabs() and list() are independent. Sequential await cost
  // both round-trips back-to-back; allSettled fires them together and lets
  // each fail in isolation.
  const [tabsResult, queuedResult] = await Promise.allSettled([
    client.scripts.tabs(),
    client.scripts.list({ needs_script: true }),
  ])

  const tabs: string[] = tabsResult.status === "fulfilled" ? tabsResult.value : []
  const error: string | null =
    tabsResult.status === "rejected"
      ? tabsResult.reason instanceof Error
        ? tabsResult.reason.message
        : "Failed to load script tabs"
      : null
  const queued: Script[] = queuedResult.status === "fulfilled" ? queuedResult.value : []
  const queueFetchFailed = queuedResult.status === "rejected"

  const briefing = computeScriptsBriefing({ queued, queueFetchFailed })

  return (
    <ScriptGenerator
      tabs={tabs}
      tabsError={error}
      idToken={idToken}
      userRole={userProfile.role}
      briefing={briefing}
    />
  )
}

// ─── Briefing computation ───────────────────────────────────────────────────
//
// On /scripts, the user is a writer sitting down to work. The briefing's job
// is to point at the one script whose shoot is soonest — so they start where
// the deadline is tightest, not the top of an alphabetized list.

function computeScriptsBriefing(input: { queued: Script[]; queueFetchFailed: boolean }): Briefing | null {
  const { queued, queueFetchFailed } = input

  if (queueFetchFailed) {
    return {
      eyebrow: "Next up",
      tone: "error",
      count: 0,
      headline: "Couldn't load the script queue",
      detail: "The queue is temporarily unreachable. Use Manual mode below to draft without it.",
      cta: null,
      secondary: [],
    }
  }

  if (queued.length === 0) {
    return {
      eyebrow: "Next up",
      tone: "calm",
      count: 0,
      headline: "Queue is empty",
      detail: "No scripts currently flagged as needing a draft. New shoots will appear here once they're added to the sheet.",
      cta: null,
      secondary: [],
    }
  }

  // Earliest upcoming shoot that still needs a script.
  const withDate = queued
    .filter(s => s.shoot_date && parseLocalDate(s.shoot_date) !== null)
    .sort((a, b) => (a.shoot_date ?? "").localeCompare(b.shoot_date ?? ""))

  const next = withDate[0] ?? null
  const now = Date.now()
  // parseLocalDate keeps the daysOut math anchored to local midnight, so a
  // shoot on tomorrow's calendar reads as +1 day instead of 0 (or -1) for
  // users west of UTC.
  const nextT = next ? parseLocalDate(next.shoot_date!) : null
  const daysOut = nextT !== null ? Math.round((nextT - now) / (24 * 60 * 60 * 1000)) : null
  const talent = next ? [next.female, next.male].filter(Boolean).join(" / ") : ""

  const when =
    daysOut === null ? null :
    daysOut < 0      ? `shot ${-daysOut}d ago` :
    daysOut === 0    ? "shoots today" :
    daysOut === 1    ? "shoots tomorrow" :
    `shoots in ${daysOut}d`

  if (!next) {
    return {
      eyebrow: "Next up",
      tone: "attention",
      count: queued.length,
      headline: `${queued.length} script${queued.length === 1 ? "" : "s"} queued — no shoot dates set`,
      detail: "Scripts are ready to draft but don't have a shoot date yet. Pick any row from the sheet to begin.",
      cta: null,
      secondary: [],
    }
  }

  const tone: Briefing["tone"] =
    daysOut !== null && daysOut < 0 ? "urgent" :
    daysOut !== null && daysOut < 3 ? "urgent" :
    daysOut !== null && daysOut < 7 ? "attention" :
    "calm"

  return {
    eyebrow: "Next up",
    tone,
    count: queued.length,
    headline: `${talent || next.id} ${when ?? ""}`.trim(),
    detail:
      `${queued.length} script${queued.length === 1 ? "" : "s"} still queued.` +
      ` Start with the shoot that's tightest on time.`,
    cta: null,
    secondary: [
      next.studio,
      next.shoot_date ? next.shoot_date.slice(0, 10) : "",
    ].filter(Boolean),
  }
}
