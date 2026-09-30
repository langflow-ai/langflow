/**
 * Single source of truth for Playwright timeouts.
 *
 * Every hardcoded `timeout: <ms>` in a spec should map to one of these.
 * Animation waits (`waitForTimeout(X)` with a documented reason) live in
 * `ANIMATIONS` so the *why* is named at the call site.
 */
export const TIMEOUTS = {
  /** Short interactions (sidebar typeahead, drag prep). */
  fast: 1_000,
  /** Single-element appears after a click. */
  short: 3_000,
  /** Modal open, listbox populated, navigation settle. */
  medium: 10_000,
  /** Page load, settings header, common assertions. */
  standard: 30_000,
  /** Component mounts after a starter project loads. */
  componentMount: 100_000,
  /** Backend operations that may queue (auto-login off, slow Windows CI). */
  long: 60_000,
  /** Build finished / stop-button hidden / large flow runs. */
  buildComplete: 120_000,
} as const;

/**
 * Documented animation/propagation waits. Use these instead of bare
 * `page.waitForTimeout(N)` — the name explains *why* the sleep is needed.
 */
export const ANIMATIONS = {
  /** Wait for the fullscreen playground overlay animation to settle. */
  fullscreenPlayground: 1_000,
  /** Wait for the publish-switch toggle to propagate to the backend. */
  publishTogglePropagation: 2_000,
  /** Wait for the new shareable-playground tab to finish mounting. */
  shareablePlaygroundMount: 3_000,
} as const;
