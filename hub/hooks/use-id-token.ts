"use client"

import { useSession } from "next-auth/react"

export function useIdToken(serverIdToken: string | undefined): string | undefined {
  const { data: session } = useSession()
  return (session as { idToken?: string } | null)?.idToken ?? serverIdToken
}
