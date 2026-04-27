"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RotateCcw } from "lucide-react"

/**
 * Drawn signature capture — canvas with mouse + touch + pen support.
 *
 * Stable behavior across Pencil/finger on iPad and mouse on desktop. The
 * caller drives lifecycle: we expose the current PNG via `onChange` (a
 * data URL string) and clear via `onClear`. The component holds no value
 * state above the canvas itself; the parent decides when the signature
 * is "complete enough" to submit.
 *
 * The canvas internally uses devicePixelRatio so strokes stay crisp on
 * Retina iPads, but the exported PNG is the on-screen size (typically
 * ~600×140 logical px) so it embeds cleanly in the agreement PDF.
 */

interface Props {
  onChange: (pngDataUrl: string | null) => void
  height?: number
  accent?: string
  disabled?: boolean
}

export function SignaturePad({
  onChange,
  height = 140,
  accent = "var(--color-lime)",
  disabled = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const drawingRef = useRef(false)
  const lastPtRef = useRef<{ x: number; y: number } | null>(null)
  const [isEmpty, setIsEmpty] = useState(true)
  const [width, setWidth] = useState(600)

  // Resize observer: keep canvas at full container width
  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current
    const update = () => setWidth(Math.max(280, Math.floor(el.clientWidth)))
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Configure canvas — devicePixelRatio scaling for crisp lines
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    const ctx = canvas.getContext("2d")
    if (!ctx) return
    ctx.scale(dpr, dpr)
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    ctx.strokeStyle = "#0a0a0a"
    ctx.lineWidth = 2.2
    // Fill white so the exported PNG has a background that prints on paper
    ctx.fillStyle = "#ffffff"
    ctx.fillRect(0, 0, width, height)
  }, [width, height])

  const getPoint = useCallback((e: PointerEvent | React.PointerEvent) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }
  }, [])

  const startStroke = (e: React.PointerEvent) => {
    if (disabled) return
    e.preventDefault()
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.setPointerCapture(e.pointerId)
    drawingRef.current = true
    lastPtRef.current = getPoint(e)
    // Mark non-empty as soon as the user touches down so the parent UI
    // can flip out of the "empty" state immediately
    setIsEmpty(false)
  }

  const continueStroke = (e: React.PointerEvent) => {
    if (!drawingRef.current || disabled) return
    e.preventDefault()
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return
    const cur = getPoint(e)
    const last = lastPtRef.current
    if (!last) return
    ctx.beginPath()
    ctx.moveTo(last.x, last.y)
    ctx.lineTo(cur.x, cur.y)
    ctx.stroke()
    lastPtRef.current = cur
  }

  const endStroke = (e: React.PointerEvent) => {
    if (!drawingRef.current) return
    drawingRef.current = false
    lastPtRef.current = null
    const canvas = canvasRef.current
    if (!canvas) return
    try {
      canvas.releasePointerCapture(e.pointerId)
    } catch {
      // capture may already be lost — no-op
    }
    onChange(canvas.toDataURL("image/png"))
  }

  const clear = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return
    ctx.fillStyle = "#ffffff"
    ctx.fillRect(0, 0, width, height)
    setIsEmpty(true)
    onChange(null)
  }

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <canvas
        ref={canvasRef}
        onPointerDown={startStroke}
        onPointerMove={continueStroke}
        onPointerUp={endStroke}
        onPointerCancel={endStroke}
        onPointerLeave={endStroke}
        style={{
          display: "block",
          width: "100%",
          background: "#ffffff",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          touchAction: "none",
          cursor: disabled ? "not-allowed" : "crosshair",
        }}
      />

      {isEmpty && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            color: "#a1a1aa",
            fontSize: 13,
            letterSpacing: "0.04em",
          }}
        >
          Sign with finger or Apple Pencil
        </div>
      )}

      {/* Baseline line — printed on the canvas isn't possible without
          shifting the drawn signature, so we draw it as a CSS overlay
          below the canvas inside the same border. */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          left: "10%",
          right: "10%",
          bottom: 28,
          height: 1,
          background: "var(--color-border)",
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginTop: 8,
          fontSize: 11,
          color: "var(--color-text-faint)",
        }}
      >
        <span style={{ fontWeight: 500, letterSpacing: "0.04em" }}>
          {isEmpty ? "Signature required" : "Signature captured"}
        </span>
        <button
          type="button"
          onClick={clear}
          disabled={disabled || isEmpty}
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            padding: "5px 10px",
            fontSize: 11,
            fontWeight: 600,
            color: isEmpty ? "var(--color-text-faint)" : "var(--color-text-muted)",
            cursor: disabled || isEmpty ? "not-allowed" : "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          <RotateCcw size={11} aria-hidden /> Clear
        </button>
      </div>
    </div>
  )
}
