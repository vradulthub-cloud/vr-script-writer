import { auth } from "@/auth"
import { api, type Approval } from "@/lib/api"
import { requireTab } from "@/lib/rbac"
import { ApprovalList } from "./approval-list"
import { ApprovalSubmit } from "./approval-submit"
import { ApprovalsPageShell } from "./approvals-page-shell"

export const dynamic = "force-dynamic"

export default async function ApprovalsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Tickets", idToken)
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
    <ApprovalsPageShell pendingCount={pendingCount}>
      {{
        review: (
          <ApprovalList
            initialApprovals={approvals}
            error={error}
            idToken={idToken}
          />
        ),
        submit: (
          <ApprovalSubmit idToken={idToken} />
        ),
      }}
    </ApprovalsPageShell>
  )
}
