import type { Metadata } from "next"
import { Geist, Geist_Mono, Anton, Newsreader } from "next/font/google"
import localFont from "next/font/local"
import { Providers } from "@/components/providers"
import "./globals.css"

// Newsreader — humanist serif used by the Writing Room redesign for hero
// titles + body paragraphs in script/description output. Matches EB Garamond
// in feel but is broader optical-size aware (the variable axis is on by
// default), so it scales cleanly from 14px form labels to 36px hero titles.
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
})

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

const generalSans = localFont({
  src: [
    { path: "../public/fonts/GeneralSans-Medium.woff2", weight: "500", style: "normal" },
    { path: "../public/fonts/GeneralSans-Semibold.woff2", weight: "600", style: "normal" },
    { path: "../public/fonts/GeneralSans-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-general-sans",
  display: "swap",
})

// Anton — condensed display face for page-level h1s (.display-hero) and the
// v2 ec-page-head title. Replaces Cabinet Grotesk (2026-04-23) because CG
// reads as the default designer-safe choice rather than a face specific to a
// production-studio context. Anton is a single-weight (400) film-slate
// grotesque — it looks like a production call-sheet title. Loaded from Google
// Fonts so there's no woff2 to ship.
const anton = Anton({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-anton",
  display: "swap",
})

export const metadata: Metadata = {
  title: "Eclatech Hub",
  description: "Production management for FPVR · VRH · VRA · NJOI",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${generalSans.variable} ${anton.variable} ${newsreader.variable} h-full`}
    >
      <body className="h-full antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
