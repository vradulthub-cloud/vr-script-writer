import { authMiddleware } from "@/auth"
import { NextResponse } from "next/server"

// Dev-only bypass: NODE_ENV + DEV_AUTH_MOCK guard. Production strips this.
const DEV_MOCK =
  process.env.NODE_ENV !== "production" && process.env.DEV_AUTH_MOCK === "1"

export const proxy = DEV_MOCK
  ? () => NextResponse.next()
  : authMiddleware

export const config = {
  // Protect all routes except static assets, login, and next-auth API
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|login|api/auth).*)",
  ],
}
