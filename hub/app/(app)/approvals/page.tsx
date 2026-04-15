import { auth } from "@/auth"
import { api, type Approval } from "@/lib/api"
import { ApprovalList } from "./approval-list"

export const dynamic = "force-dynamic"

export default async function ApprovalsPage() {
  const session = await auth()
  const client = api(session)

  let approvals: Approval[] = []
  let error: string | null = null

  try {
    approvals = await client.approvals.list()
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load approvals"
  }

  const pendingCount = approvals.filter(a => a.status === "Pending").length

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-semibold tracking-tight" style={{ fontSize: 16, color: "var(--color-text)" }}>
            Approvals
          </h1>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
            {pendingCount > 0
              ? `${pendingCount} pending decision${pendingCount !== 1 ? "s" : ""}`
              : "No pending approvals"}
          </p>
        </div>
      </div>
      <ApprovalList
        initialApprovals={approvals}
        error={error}
        idToken={(session as { idToken?: string } | null)?.idToken}
      />
    </div>
  )
}
