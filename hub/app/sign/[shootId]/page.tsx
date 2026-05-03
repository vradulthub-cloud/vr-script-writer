import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { SignView } from "./sign-view"

export default async function SignPage({
  params,
  searchParams,
}: {
  params: Promise<{ shootId: string }>
  searchParams: Promise<Record<string, string>>
}) {
  const session = await auth()
  if (!session) redirect("/login")

  const { shootId } = await params
  const sp = await searchParams

  return (
    <SignView
      shootId={shootId}
      talent={sp.talent ?? ""}
      display={sp.display ?? sp.talent ?? ""}
      studio={sp.studio ?? ""}
    />
  )
}
