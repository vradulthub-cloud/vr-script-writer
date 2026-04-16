export { auth as proxy } from "@/auth"

export const config = {
  // Protect all routes except static assets, login, and next-auth API
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|login|api/auth).*)",
  ],
}
