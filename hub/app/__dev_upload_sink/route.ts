/**
 * Dev-only sink for the simulated multipart upload PUTs.
 *
 * The dev mock returns presigned URLs that point here so the orchestrator's
 * PUT/concurrency/retry logic stays exercised end-to-end without hitting
 * MEGA. We absorb the bytes and return a fake ETag — same shape the real
 * S3 endpoint would produce.
 *
 * Only mounted; never called from production.
 */
import { NextRequest, NextResponse } from "next/server"

export const dynamic = "force-dynamic"

export async function PUT(req: NextRequest): Promise<Response> {
  const params = req.nextUrl.searchParams
  const part = params.get("part") ?? "0"
  const uploadId = params.get("upload_id") ?? "dev-mock"
  // Drain the body so the request closes cleanly even with a 64 MB chunk.
  const reader = req.body?.getReader()
  let bytes = 0
  if (reader) {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (value) bytes += value.byteLength
    }
  }
  const etag = `"dev-${uploadId}-${part}-${bytes}"`
  return new NextResponse(null, {
    status: 200,
    headers: {
      ETag: etag,
      "Access-Control-Expose-Headers": "ETag",
    },
  })
}

export async function OPTIONS(): Promise<Response> {
  return new NextResponse(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "PUT, OPTIONS",
      "Access-Control-Allow-Headers": "*",
      "Access-Control-Expose-Headers": "ETag",
    },
  })
}
