import { auth } from "@/auth"
import { api, cachedUsersMe, type Ticket, type UserProfile } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { TicketList } from "./ticket-list"

export const dynamic = "force-dynamic"

/**
 * Tickets page — server entry.
 *
 * The redundant Open Tickets / In Review / Closed tab strip that used to
 * live above the list got cut. The status pill row inside <TicketList>
 * (Active / All / New / In Progress / In Review / Closed) covers the same
 * states with finer granularity, so the tab strip was just chrome.
 *
 * Approvals are intentionally not fetched — the workflow is paused; see
 * /approvals which renders a "Paused" notice for direct visitors.
 */
export default async function TicketsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Tickets", idToken)
  const client = api(session)

  let tickets: Ticket[]            = []
  let ticketsError: string | null   = null
  let users: UserProfile[]         = []
  let userRole = "editor"

  const [ticketsRes, usersRes, meRes] = await Promise.allSettled([
    client.tickets.list(),
    client.users.list(),
    cachedUsersMe(idToken),
  ])

  if (ticketsRes.status === "fulfilled") {
    tickets = ticketsRes.value
  } else {
    ticketsError = ticketsRes.reason instanceof Error
      ? ticketsRes.reason.message : "Failed to load tickets"
  }

  if (usersRes.status === "fulfilled") users = usersRes.value
  if (meRes.status    === "fulfilled" && meRes.value) {
    userRole = (meRes.value.role ?? "editor").toLowerCase()
  }

  return (
    <TicketList
      tickets={tickets}
      users={users}
      error={ticketsError}
      idToken={idToken}
      userRole={userRole}
    />
  )
}
