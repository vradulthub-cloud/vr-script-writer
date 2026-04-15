import { auth } from "@/auth"
import { NextResponse } from "next/server"

export default auth((req) => {
  // Redirect unauthenticated users to /login instead of showing 401 errors
  if (!req.auth && !req.nextUrl.pathname.startsWith("/login")) {
    return NextResponse.redirect(new URL("/login", req.url))
  }
})

export const config = {
  // Protect all routes except Next.js internals, static assets, and auth endpoints
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico).*)"],
}
