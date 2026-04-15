import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
    }),
  ],
  pages: {
    signIn: "/login",
    error: "/login",
  },
  callbacks: {
    // Persist the Google ID token so we can forward it to the FastAPI backend.
    // Google ID tokens expire after 1 hour — store the expiry and force
    // re-login when it lapses so the API never sees a stale token.
    async jwt({ token, account }) {
      if (account?.id_token) {
        token.idToken = account.id_token
        // 5-minute buffer before the actual 1-hour Google expiry
        token.idTokenExpires = Date.now() + 55 * 60 * 1000
      }
      if (token.idTokenExpires && Date.now() > (token.idTokenExpires as number)) {
        // Returning null invalidates the session → NextAuth redirects to /login
        return null
      }
      return token
    },
    async session({ session, token }) {
      // Expose idToken on the session object for API calls
      session.idToken = token.idToken as string | undefined
      return session
    },
  },
})
