<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Visual verification: use `npm run dev:mock`

Before claiming any UI change is "verified", run the dev-mock server and open the page in a browser/preview. It bypasses Google OAuth and serves fixtures so you can navigate the whole app without a real backend.

```bash
npm run dev:mock
```

Flags: `DEV_AUTH_MOCK=1` + `NEXT_PUBLIC_DEV_AUTH_MOCK=1`. Both are guarded by `NODE_ENV !== "production"` — Vercel builds dead-code-eliminate the entire mock branch, so there's no way it ships. Verified with `NODE_ENV=production npx next build`.

Fixtures live in `lib/dev-fixtures.ts`; routing in `lib/dev-mock-api.ts`; auth short-circuit in `auth.ts` + `proxy.ts`; thumbnail URLs resolve through `thumbnailUrl()` in `lib/api.ts` (dev uses picsum.photos seeds for realistic placeholder images).

**Do not call a change "verified" based on typecheck or static scan alone** — you must actually render the page in the mock and confirm it looks right.
