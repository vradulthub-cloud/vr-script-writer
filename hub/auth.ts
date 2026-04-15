import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  ],
  pages: {
    signIn: "/login",
    error: "/login",
  },
  callbacks: {
    // Persist the Google ID token so we can forward it to the FastAPI backend
    async jwt({ token, account }) {
      if (account?.id_token) {
        token.idToken = account.id_token
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
