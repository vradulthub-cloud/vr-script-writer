"use client"

import { useState, useRef } from "react"

interface StreamState {
  output: string
  streaming: boolean
  error: string | null
}

export function useStream() {
  const [state, setState] = useState<StreamState>({
    output: "", streaming: false, error: null
  })
  const abortRef = useRef<AbortController | null>(null)

  async function start(url: string, token: string | undefined, body: unknown) {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    setState({ output: "", streaming: true, error: null })

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
              setState(s => ({ ...s, output: s.output + msg.text }))
            } else if (msg.type === "error") {
              setState(s => ({ ...s, error: msg.error }))
            }
          } catch {}
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setState(s => ({ ...s, error: e instanceof Error ? e.message : "Stream failed" }))
      }
    } finally {
      setState(s => ({ ...s, streaming: false }))
    }
  }

  function stop() { abortRef.current?.abort() }
  function reset() { setState({ output: "", streaming: false, error: null }) }

  return { ...state, start, stop, reset }
}
