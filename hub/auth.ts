import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

// Dev-only bypass: NODE_ENV check is inlined by Next.js, so production bundles
// dead-code-eliminate this branch entirely. Opt-in via DEV_AUTH_MOCK=1.
const DEV_MOCK =
  process.env.NODE_ENV !== "production" && process.env.DEV_AUTH_MOCK === "1"

const MOCK_SESSION = {
  user: {
    name: "Dev Admin",
    email: "dev@eclatech.test",
    image: null,
  },
  idToken: "DEV_MOCK_TOKEN",
  expires: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
} as unknown as import("next-auth").Session

async function refreshIdToken(refreshToken: string): Promise<{
  idToken: string
  accessToken: string
  idTokenExpires: number
} | null> {
  try {
    const res = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: process.env.AUTH_GOOGLE_ID!,
        client_secret: process.env.AUTH_GOOGLE_SECRET!,
        grant_type: "refresh_token",
        refresh_token: refreshToken,
      }),
    })
    const data = await res.json()
    if (!res.ok || !data.id_token) throw new Error(data.error ?? "Refresh failed")
    return {
      idToken: data.id_token,
      accessToken: data.access_token,
      // 5-minute buffer before actual expiry
      idTokenExpires: Date.now() + ((data.expires_in as number) - 300) * 1000,
    }
  } catch (err) {
    console.error("[auth] Token refresh failed:", err)
    return null
  }
}

const nextAuth = NextAuth({
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
      // access_type: offline gives us a refresh_token so we can renew the ID token silently
      authorization: { params: { access_type: "offline", prompt: "consent" } },
    }),
  ],
  pages: {
    signIn: "/login",
    error: "/login",
  },
  callbacks: {
    async jwt({ token, account }) {
      // Initial sign-in: persist all tokens
      if (account) {
        return {
          ...token,
          idToken: account.id_token,
          accessToken: account.access_token,
          refreshToken: account.refresh_token ?? token.refreshToken,
          // account.expires_at is a Unix timestamp in seconds
          idTokenExpires: (account.expires_at ?? 0) * 1000 - 5 * 60 * 1000,
        }
      }

      // Token still valid — return as-is
      if (Date.now() < ((token.idTokenExpires as number) ?? 0)) {
        return token
      }

      // Token expired — try to refresh silently
      if (!token.refreshToken) {
        // Old session without a refresh_token: force re-login
        return null
      }
      const refreshed = await refreshIdToken(token.refreshToken as string)
      if (!refreshed) return null // Refresh failed → force re-login
      return { ...token, ...refreshed }
    },
    async session({ session, token }) {
      session.idToken = token.idToken as string | undefined
      return session
    },
  },
})

export const handlers = nextAuth.handlers
export const signIn   = nextAuth.signIn
export const signOut  = nextAuth.signOut

// Real NextAuth middleware handler — used by proxy.ts unconditionally so the
// exported middleware always returns a Response-shape.
export const authMiddleware = nextAuth.auth

// Server-component helper. In dev-mock mode this returns a hardcoded admin
// session; in prod it delegates to NextAuth.
export const auth: typeof nextAuth.auth = DEV_MOCK
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ? ((async () => MOCK_SESSION) as any)
  : nextAuth.auth
