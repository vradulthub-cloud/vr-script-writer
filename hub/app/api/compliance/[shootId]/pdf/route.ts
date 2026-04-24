import { auth } from "@/auth"
import { NextResponse } from "next/server"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8502"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ shootId: string }> },
) {
  const session = await auth()
  if (!session) return new NextResponse("Unauthorized", { status: 401 })

  const { shootId } = await params
  const { searchParams } = new URL(request.url)
  const talent = searchParams.get("talent") ?? ""

  const idToken = (session as { idToken?: string })?.idToken
  const headers: Record<string, string> = {}
  if (idToken) headers["Authorization"] = `Bearer ${idToken}`

  const upstream = `${API_BASE}/api/compliance/shoots/${encodeURIComponent(shootId)}/pdf?talent=${encodeURIComponent(talent)}`
  let res: Response
  try {
    res = await fetch(upstream, { headers })
  } catch {
    return new NextResponse("Backend unavailable", { status: 502 })
  }

  if (!res.ok) return new NextResponse("PDF not found", { status: res.status })

  const bytes = await res.arrayBuffer()
  return new NextResponse(bytes, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="${talent}.pdf"`,
    },
  })
}
