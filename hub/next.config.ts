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
}

export default nextConfig
