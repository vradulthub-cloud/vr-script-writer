/**
 * Route-segment loading state for the authenticated app. Rendered while a
 * server component suspends (e.g. waiting on users.me(), tickets.list()).
 * Without this, clicking nav produces an unresponsive feel — link flips
 * highlight but the panel doesn't change until the fetch resolves.
 */
export default function AppLoading() {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      style={{
        padding: "48px 0",
        fontSize: 11,
        color: "var(--color-text-faint)",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
      }}
    >
      Loading…
    </div>
  )
}
