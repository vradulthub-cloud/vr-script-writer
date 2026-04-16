"use client"

import { useSession } from "next-auth/react"

export function useIdToken(serverIdToken: string | undefined): string | undefined {
  const { data: session, status } = useSession()
  // If explicitly unauthenticated, don't fall back to a stale server-side token
  if (status === "unauthenticated") return undefined
  return (session as { idToken?: string } | null)?.idToken ?? serverIdToken
}
