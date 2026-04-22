import { auth } from "@/auth"
import { api, cachedUsersMe, type Ticket, type UserProfile } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { TicketsTabs } from "./tickets-tabs"

export const dynamic = "force-dynamic"

/**
 * Tickets page — server entry.
 *
 * Approvals are intentionally NOT fetched here anymore. The Approvals tab
 * was removed from /tickets per product call (team isn't using approvals
 * yet); the data fetch went with it to save a round trip on every load.
 * The /approvals route is still live for direct deep-links.
 */
export default async function TicketsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Tickets", idToken)
  const client = api(session)
  const v2 = await isEclatechV2()

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
    <div>
      <TicketsTabs
        tickets={tickets}
        ticketsError={ticketsError}
        users={users}
        idToken={idToken}
        userRole={userRole}
        v2={v2}
      />
    </div>
  )
}
