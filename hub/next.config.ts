import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // Use standalone output only for Windows self-hosted deploy (node server.js).
  // Vercel manages its own build pipeline and doesn't need this.
  output: process.env.VERCEL ? undefined : "standalone",

  images: {
    remotePatterns: [
      { protocol: "https", hostname: "lh3.googleusercontent.com" }, // Google avatars
    ],
  },

  // Compress responses — ~60-70% smaller HTML/JSON payloads
  compress: true,

  // Tell Next to aggressively tree-shake these packages during build. Works
  // with Turbopack; no effect on modern lucide-react (already ESM + per-icon
  // exports) but harmless. Anthropic/Claude sessions trying `modularizeImports`
  // on lucide-react 1.x will hit default-export errors — use this instead.
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
}

export default nextConfig
