"use client"

import { useEffect } from "react"
import type { Scene } from "@/lib/api"
import { SceneDetail } from "@/app/(app)/missing/scene-detail"

/**
 * Centered modal that hosts the SceneDetail panel. Used by:
 *   - Grail Assets page (clicked card / row → modal)
 *   - Dashboard "Recent activity" feed (clicked row → modal in place)
 *
 * Backdrop click + ESC close. Body scroll is locked while open. Inner
 * content scrolls if it overflows.
 */
export function SceneDetailModal({
  scene,
  idToken,
  onClose,
  onSceneUpdate,
}: {
  scene: Scene | null
  idToken?: string
  onClose: () => void
  onSceneUpdate: (updated: Scene) => void
}) {
  useEffect(() => {
    if (!scene) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [scene, onClose])

  useEffect(() => {
    if (!scene) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = prev }
  }, [scene])

  if (!scene) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Scene ${scene.id} details`}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "min(5vh, 32px)",
        background: "color-mix(in srgb, var(--color-base) 70%, transparent)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
        animation: "scene-modal-fade 180ms ease-out",
      }}
    >
      <style jsx>{`
        @keyframes scene-modal-fade {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes scene-modal-rise {
          from { opacity: 0; transform: translateY(8px) scale(0.985); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(720px, 92vw)",
          maxWidth: 720,
          maxHeight: "calc(100vh - min(10vh, 64px))",
          display: "flex",
          flexDirection: "column",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          boxShadow: "0 24px 60px -12px rgba(0,0,0,0.55), 0 8px 16px -8px rgba(0,0,0,0.4)",
          animation: "scene-modal-rise 220ms cubic-bezier(0.16, 1, 0.3, 1)",
          overflow: "hidden",
        }}
      >
        <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
          <SceneDetail
            key={scene.id}
            scene={scene}
            idToken={idToken}
            onClose={onClose}
            onSceneUpdate={onSceneUpdate}
          />
        </div>
      </div>
    </div>
  )
}
