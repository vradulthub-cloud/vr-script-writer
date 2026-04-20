import { auth } from "@/auth"
import { api, cachedUsersMe, type Approval, type Ticket, type UserProfile } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { isEclatechV2 } from "@/lib/eclatech-flag"
import { PageHeader } from "@/components/ui/page-header"
import { TicketsTabs } from "./tickets-tabs"

export const dynamic = "force-dynamic"

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

  const pendingCount = approvals.filter(a => a.status === "Pending").length
  const openCount    = tickets.filter(t => ["New", "Approved", "In Progress"].includes(t.status)).length
  const totalCount   = pendingCount + openCount

  return (
    <div>
      <PageHeader
        title="Tickets"
        eyebrow={
          [
            totalCount   ? `${totalCount} items`        : null,
            pendingCount ? `${pendingCount} approvals`  : null,
            openCount    ? `${openCount} open`          : null,
          ].filter(Boolean).join(" · ") || "Queue"
        }
        actions={
          <button
            style={{
              padding: "7px 14px",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              background: "var(--color-lime)",
              color: "#000",
              border: "none",
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            + New Ticket
          </button>
        }
      />

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
