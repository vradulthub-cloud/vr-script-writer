import { ApiError } from "@/lib/api"

/**
 * Converts an unknown catch value into a user-readable error message.
 * Maps HTTP status codes to plain-language descriptions with action hints.
 */
export function formatApiError(e: unknown, context?: string): string {
  if (e instanceof ApiError) {
    switch (e.status) {
      case 401: return "Session expired — refresh the page"
      case 403: return "You don't have permission for this action"
      case 404: return "Not found"
      case 422: return "Invalid input — check your data"
      case 429: return "Too many requests — wait a moment and try again"
      case 500:
      case 502:
      case 503:
      case 504: return "Server error — try again in a moment"
      default:  return context ? `${context} failed (${e.status})` : `Request failed (${e.status})`
    }
  }
  if (
    e instanceof TypeError &&
    (e.message.includes("fetch") || e.message.includes("network") || e.message.includes("Failed to fetch"))
  ) {
    return "Can't reach the server — check your connection"
  }
  if (e instanceof Error && e.message && !/^\d{3}$/.test(e.message)) {
    return e.message
  }
  return context ? `${context} failed` : "Something went wrong"
}
