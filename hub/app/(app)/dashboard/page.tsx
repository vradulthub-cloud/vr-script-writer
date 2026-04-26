import { Suspense } from "react"
import { auth } from "@/auth"
import { PageHeader } from "@/components/ui/page-header"
import {
  BriefingSection,
  BriefingSkeleton,
  CalendarSection,
  CalendarSkeleton,
  HealthBadge,
  NotificationSection,
  NotificationSkeleton,
  SceneStripSection,
  StripSkeleton,
  TriageSection,
  TriageSkeleton,
} from "./sections"

// `force-dynamic` removed — each Suspense boundary owns its own dynamism via
// the React `cache()`-wrapped fetchers in ./data.ts. The shell (header,
// greeting, layout) is now static-by-default and ships as the first byte;
// each section streams in independently as its backend call resolves.
// Previously this page awaited Promise.allSettled of 6 API calls before
// emitting any HTML — the slowest call dictated TTFB.
export const dynamic = "force-dynamic"

export default async function DashboardPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken

  // The team works on LA time; Vercel renders in UTC. Without a fixed timeZone
  // the eyebrow flips to tomorrow's weekday once UTC rolls past midnight while
  // it's still afternoon/evening in LA.
  const TZ = "America/Los_Angeles"
  const now       = new Date()
  const laHour    = Number(new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", hour12: false }).format(now))
  const greeting  = laHour < 12 ? "Good morning" : laHour < 17 ? "Good afternoon" : "Good evening"
  const firstName = session?.user?.name?.split(" ")[0] ?? "there"
  const eyebrow   = now
    .toLocaleDateString("en-US", { timeZone: TZ, weekday: "short", month: "short", day: "numeric" })
    .toUpperCase()

  return (
    <div style={{ maxWidth: 1400 }}>
      <PageHeader
        compact
        title={`${greeting}, ${firstName}`}
        eyebrow={eyebrow}
        actions={
          <Suspense fallback={null}>
            <HealthBadge idToken={idToken} />
          </Suspense>
        }
      />

      <Suspense fallback={<BriefingSkeleton />}>
        <BriefingSection idToken={idToken} />
      </Suspense>

      <Suspense fallback={<CalendarSkeleton />}>
        <CalendarSection idToken={idToken} />
      </Suspense>

      <Suspense fallback={<StripSkeleton />}>
        <SceneStripSection idToken={idToken} />
      </Suspense>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">
        <div className="flex flex-col gap-6">
          <Suspense fallback={<TriageSkeleton />}>
            <TriageSection idToken={idToken} />
          </Suspense>
        </div>
        <div className="flex flex-col gap-3.5">
          <Suspense fallback={<NotificationSkeleton />}>
            <NotificationSection idToken={idToken} />
          </Suspense>
        </div>
      </div>
    </div>
  )
}
