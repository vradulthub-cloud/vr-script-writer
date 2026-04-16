import nextDynamic from "next/dynamic"
import { auth } from "@/auth"

const TitleGenerator = nextDynamic(() => import("./title-generator").then(m => m.TitleGenerator))

export const dynamic = "force-dynamic"

export default async function TitlesPage() {
  const session = await auth()

  return <TitleGenerator idToken={(session as { idToken?: string } | null)?.idToken} />
}
