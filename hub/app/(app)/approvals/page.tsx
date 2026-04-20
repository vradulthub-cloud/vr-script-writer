import { redirect } from "next/navigation"

// Approvals are now a sub-tab inside /tickets
export default function ApprovalsPage() {
  redirect("/tickets")
}
