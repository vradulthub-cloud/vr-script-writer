import nextDynamic from "next/dynamic"
import { auth } from "@/auth"
import { requireTab } from "@/lib/rbac"

const TitleGenerator = nextDynamic(() => import("./title-generator").then(m => m.TitleGenerator))

export const dynamic = "force-dynamic"

export default async function TitlesPage() {
  const session = await auth()
  const idToken = (session as { idToken?: string } | null)?.idToken
  await requireTab("Titles", idToken)

  return <TitleGenerator idToken={idToken} />
}
