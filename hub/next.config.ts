import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // Standalone output: creates a self-contained bundle in .next/standalone
  // that can be run with `node server.js` — no node_modules needed on the server.
  output: "standalone",
}

export default nextConfig
