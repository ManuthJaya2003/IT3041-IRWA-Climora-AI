/** Tiny pub/sub so quota displays refresh the moment a query completes,
 *  instead of waiting for the next poll interval. */

export const USAGE_EVENT = 'climora:usage-changed'

export function notifyUsageChanged(): void {
  try {
    window.dispatchEvent(new Event(USAGE_EVENT))
  } catch {
    // Non-browser environments — safe to ignore.
  }
}

export function onUsageChanged(handler: () => void): () => void {
  window.addEventListener(USAGE_EVENT, handler)
  return () => window.removeEventListener(USAGE_EVENT, handler)
}
