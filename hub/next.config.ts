import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // The FastAPI backend is called directly via NEXT_PUBLIC_API_URL.
  // No proxy needed — the API client builds the full URL.
  //
  // Production: both services run behind Tailscale; update NEXT_PUBLIC_API_URL
  // to the Windows machine's Tailscale URL on port 8502.
}

export default nextConfig
