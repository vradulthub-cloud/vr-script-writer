"use client"

import { useState, useRef, useCallback } from "react"

interface StreamState {
  output: string
  streaming: boolean
  error: string | null
  reconnecting: boolean
  attempts: number
}

const MAX_RECONNECT_ATTEMPTS = 3

/**
 * POST-based SSE client. Backend endpoints (/api/scripts/generate,
 * /api/descriptions/generate, /api/compilations/ideas, /generate) return
 * a text/event-stream but are initiated with a POST body, so a regular
 * EventSource won't work (EventSource is GET-only).
 *
 * Mid-stream drops (network hiccup, server-side close) auto-retry with
 * exponential backoff up to MAX_RECONNECT_ATTEMPTS. The backend doesn't
 * support resume-from-token, so each retry restarts the generation; the
 * accumulated output is cleared at retry so the new stream doesn't append
 * on top of the old partial.
 */
export function useStream() {
  const [state, setState] = useState<StreamState>({
    output: "", streaming: false, error: null, reconnecting: false, attempts: 0,
  })
  const abortRef = useRef<AbortController | null>(null)
  const lastArgsRef = useRef<{ url: string; token: string | undefined; body: unknown } | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearRetry = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  const runOnce = useCallback(async (url: string, token: string | undefined, body: unknown, attempt: number) => {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    // On first attempt the caller already cleared state via start(); on
    // retries we clear output so new stream doesn't pile onto partial.
    setState(s => ({
      output: attempt === 0 ? s.output : "",
      streaming: true,
      error: null,
      reconnecting: false,
      attempts: attempt,
    }))

    let hadAnyOutput = false
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`${res.status}: ${text}`)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split("\n")
        buf = lines.pop()!
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const msg = JSON.parse(line.slice(6))
            if (msg.type === "text") {
              hadAnyOutput = true
              setState(s => ({ ...s, output: s.output + msg.text }))
            } else if (msg.type === "error") {
              setState(s => ({ ...s, error: msg.error }))
            }
          } catch {}
        }
      }
      setState(s => ({ ...s, streaming: false }))
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setState(s => ({ ...s, streaming: false }))
        return
      }
      // Retry only if we were mid-stream (partial output) or connection
      // failed before any 4xx/5xx — status-coded errors mean the backend
      // rejected the request, so retrying won't help.
      const msg = e instanceof Error ? e.message : "Stream failed"
      const isClientError = /^4\d\d:/.test(msg)
      const canRetry = !isClientError && attempt + 1 < MAX_RECONNECT_ATTEMPTS
      if (canRetry && lastArgsRef.current) {
        const delay = 500 * Math.pow(2, attempt) // 500, 1000, 2000
        setState(s => ({ ...s, streaming: false, reconnecting: true, error: hadAnyOutput ? "Connection dropped — retrying…" : null }))
        retryTimerRef.current = setTimeout(() => {
          if (!lastArgsRef.current) return
          void runOnce(lastArgsRef.current.url, lastArgsRef.current.token, lastArgsRef.current.body, attempt + 1)
        }, delay)
        return
      }
      setState(s => ({ ...s, streaming: false, reconnecting: false, error: msg }))
    }
  }, [])

  const start = useCallback(async (url: string, token: string | undefined, body: unknown) => {
    clearRetry()
    lastArgsRef.current = { url, token, body }
    setState({ output: "", streaming: true, error: null, reconnecting: false, attempts: 0 })
    await runOnce(url, token, body, 0)
  }, [clearRetry, runOnce])

  const stop = useCallback(() => {
    clearRetry()
    lastArgsRef.current = null
    abortRef.current?.abort()
    setState(s => ({ ...s, streaming: false, reconnecting: false }))
  }, [clearRetry])

  const resume = useCallback(() => {
    if (!lastArgsRef.current) return
    clearRetry()
    const { url, token, body } = lastArgsRef.current
    void runOnce(url, token, body, 0)
  }, [clearRetry, runOnce])

  const reset = useCallback(() => {
    clearRetry()
    lastArgsRef.current = null
    setState({ output: "", streaming: false, error: null, reconnecting: false, attempts: 0 })
  }, [clearRetry])

  return { ...state, start, stop, resume, reset }
}
