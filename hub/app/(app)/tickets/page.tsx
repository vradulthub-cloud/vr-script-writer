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

  try {
    tickets = await client.tickets.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load tickets"
  }

  // Fetch users for assignee picker (non-critical — falls back to text input)
  try {
    users = await client.users.list()
  } catch {
    // Silently fail
  }

  return (
    <div>
      <div className="mb-6">
        <h1>Tickets</h1>
      </div>
      <TicketList tickets={tickets} users={users} error={error} idToken={idToken} />
    </div>
  )
}
