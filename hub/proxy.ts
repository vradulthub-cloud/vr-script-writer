import { authMiddleware } from "@/auth"
import { NextRequest, NextResponse } from "next/server"

// Dev-only bypass: NODE_ENV + DEV_AUTH_MOCK guard. Production strips this.
const DEV_MOCK =
  process.env.NODE_ENV !== "production" && process.env.DEV_AUTH_MOCK === "1"

// Temporary production bypass — set SKIP_AUTH=1 in Vercel env vars to let
// unauthenticated traffic through (e.g. for design review). Remove when done.
const SKIP_AUTH = process.env.SKIP_AUTH === "1"

const authProxy = (DEV_MOCK || SKIP_AUTH) ? () => NextResponse.next() : authMiddleware

// Thin wrapper that honors ?eclatech=v1|v2|off by setting/clearing a cookie,
// then hands off to the auth middleware. Only strips the param and redirects
// when the param is present — otherwise it's a pass-through. V2 is the
// default now; ?eclatech=v1 is the per-user rollback escape hatch.
export function proxy(req: NextRequest) {
  const v = req.nextUrl.searchParams.get("eclatech")
  if (v === "v1" || v === "v2" || v === "off") {
    const url = new URL(req.nextUrl)
    url.searchParams.delete("eclatech")
    const res = NextResponse.redirect(url)
    if (v === "v1") {
      // Pin old chrome for this browser — default is V2.
      res.cookies.set("eclatech", "v1", { path: "/", sameSite: "lax" })
    } else {
      // v2 or off → clear the cookie so the default (V2) takes over.
      res.cookies.delete("eclatech")
    }
    return res
  }
  return (authProxy as (r: NextRequest) => ReturnType<typeof NextResponse.next>)(req)
}

export const config = {
  // Protect all routes except static assets, login, and next-auth API
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|login|api/auth|prototype).*)",
  ],
}
