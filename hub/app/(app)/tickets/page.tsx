import { auth } from "@/auth"
import { api, type Ticket, type UserProfile } from "@/lib/api"
import { TicketList } from "./ticket-list"

export const dynamic = "force-dynamic"

export default async function TicketsPage() {
  const session = await auth()
  const client = api(session)
  const idToken = (session as { idToken?: string } | null)?.idToken

  let tickets: Ticket[] = []
  let error: string | null = null
  let users: UserProfile[] = []

  const [ticketsRes, usersRes] = await Promise.allSettled([
    client.tickets.list(),
    client.users.list(),
  ])

  if (ticketsRes.status === "fulfilled") {
    tickets = ticketsRes.value
  } else {
    error = ticketsRes.reason instanceof Error ? ticketsRes.reason.message : "Failed to load tickets"
  }

  if (usersRes.status === "fulfilled") {
    users = usersRes.value
  }

  return <TicketList tickets={tickets} users={users} error={error} idToken={idToken} />
}
