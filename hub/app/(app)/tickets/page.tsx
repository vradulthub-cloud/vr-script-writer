import { auth } from "@/auth"
import { api, cachedUsersMe, type Ticket, type UserProfile } from "@/lib/api"
import { TicketList } from "./ticket-list"

export const dynamic = "force-dynamic"

export default async function TicketsPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

  let tickets: Ticket[] = []
  let error: string | null = null
  let users: UserProfile[] = []
  let userRole = "editor"

  const [ticketsRes, usersRes, meRes] = await Promise.allSettled([
    client.tickets.list(),
    client.users.list(),
    cachedUsersMe(idToken),
  ])

  if (ticketsRes.status === "fulfilled") {
    tickets = ticketsRes.value
  } else {
    error = ticketsRes.reason instanceof Error ? ticketsRes.reason.message : "Failed to load tickets"
  }

  if (usersRes.status === "fulfilled") {
    users = usersRes.value
  }

  if (meRes.status === "fulfilled" && meRes.value) {
    userRole = (meRes.value.role ?? "editor").toLowerCase()
  }

  return <TicketList tickets={tickets} users={users} error={error} idToken={idToken} userRole={userRole} />
}
