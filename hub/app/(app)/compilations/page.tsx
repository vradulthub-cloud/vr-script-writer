import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { requireTab } from "@/lib/rbac"

const CompBuilder = nextDynamic(() => import("./comp-builder").then(m => m.CompBuilder))

export const dynamic = "force-dynamic"

// The page used to fetch 200 scenes server-side before paint, because the
// Builder mode needs them for the multiselect. Ideas mode and Existing mode
// don't — they each load their own data. Now we defer the scene fetch into
// the Builder client component so a user landing on Ideas/Existing doesn't
// pay for it.
export default async function CompilationsPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Compilations", idToken)

  return <CompBuilder idToken={idToken} />
}
