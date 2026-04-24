export const dynamic = "force-dynamic"
export function GET() {
  return Response.json({ SKIP_AUTH: process.env.SKIP_AUTH ?? "not-set" })
}
