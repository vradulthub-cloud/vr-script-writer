import { auth } from "@/auth"
import { api, cachedUsersMe, type Approval, type Ticket, type UserProfile } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { TicketsTabs } from "./tickets-tabs"

export const dynamic = "force-dynamic"

/**
 * Tickets page — server entry.
 *
 * Layout note: the outer page used to render its own <PageHeader> with a
 * "+ New Ticket" button that had no click handler (a holdover from an
 * earlier prototype). The TicketList component already owns the page
 * header, the working create-modal trigger, and all filter UI — so this
 * page just fetches data and hands it to the tabs.
 */
export default async function TicketsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Tickets", idToken)
  const client = api(session)
  const v2 = await isEclatechV2()

  let approvals: Approval[]        = []
  let approvalsError: string | null = null
  let tickets: Ticket[]            = []
  let ticketsError: string | null   = null
  let users: UserProfile[]         = []
  let userRole = "editor"

  const [approvalsRes, ticketsRes, usersRes, meRes] = await Promise.allSettled([
    client.approvals.list(),
    client.tickets.list(),
    client.users.list(),
    cachedUsersMe(idToken),
  ])

  if (approvalsRes.status === "fulfilled") {
    approvals = approvalsRes.value
  } else {
    approvalsError = approvalsRes.reason instanceof Error
      ? approvalsRes.reason.message : "Failed to load approvals"
  }

  if (ticketsRes.status === "fulfilled") {
    tickets = ticketsRes.value
  } else {
    ticketsError = ticketsRes.reason instanceof Error
      ? ticketsRes.reason.message : "Failed to load tickets"
  }

  if (usersRes.status  === "fulfilled") users    = usersRes.value
  if (meRes.status     === "fulfilled" && meRes.value) {
    userRole = (meRes.value.role ?? "editor").toLowerCase()
  }

  return (
    <div>
      <TicketsTabs
        approvals={approvals}
        approvalsError={approvalsError}
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
