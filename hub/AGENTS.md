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

# Styling system — two parallel approaches (intentional, in transition)

The hub has two coexisting styling idioms. Both are valid; pick the right one for the surface you're building.

**1. `ec-` CSS class primitives** (defined in `app/globals.css`)
- `ec-block`, `ec-strip`, `ec-stats`, `ec-cal`, `ec-pill`, `ec-chip`, `ec-row`, `ec-ctab`, `ec-seg`, `ec-col`, `ec-split`, `ec-btn`, `ec-age`, `ec-list`, `ec-editor-head`, `ec-editor-body`, `ec-prose`, `ec-page-head`, `ec-studio-chip`, `ec-bar`, `ec-filters`
- Use for: dashboard, revenue, scene strips, calendars, segmented controls, list rows, page heads
- Pro: design-token-bound, themable, easier to audit consistency
- Con: harder to reason about per-instance variation; less type safety

**2. React inline style components** (in `components/ui/`)
- `Panel`, `PageHeader`, `TodayBriefing`, `FilterTabs`, `CommandPalette`, `HelpModal`, etc.
- Use for: complex stateful components with per-instance variation, modals, popovers, dynamic widgets
- Pro: type-safe, testable, encapsulated
- Con: magic-number font sizes, harder to enforce consistency without discipline

**When to pick which:**
- New layout primitive used 3+ places? → `ec-` class in globals.css
- Stateful, per-instance configurable, or carries domain logic? → React component
- Both? → React component that internally renders `ec-` classes

**Existing inconsistencies are known.** The two systems will eventually converge, but mixing them today is fine as long as:
- New surfaces don't introduce a *third* styling pattern (no Tailwind utility soup, no CSS-in-JS libraries, no styled-components)
- Magic numbers in inline styles map to CSS custom properties when reasonable (`var(--text-xs)` not `fontSize: 11`)
- Studio colors and lime always come from CSS variables, never hex literals
