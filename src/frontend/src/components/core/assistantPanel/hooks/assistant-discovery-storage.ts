/**
 * Persistent flag tracking whether the user has discovered the Langflow
 * Assistant. Used to suppress the onboarding affordances ("New" pill on the
 * canvas controls button + idle tooltip) once the user has acknowledged the
 * feature.
 *
 * Two triggers flip the flag to ``true`` permanently:
 *   1. The user opens the assistant for the first time.
 *   2. The user clicks the "X" on the onboarding tooltip.
 *
 * Either action proves the user has noticed the button — repeated nudges
 * after that are just noise. Best-effort: a localStorage failure (private
 * browsing, quota) is treated as "not discovered" so the affordances still
 * surface; nothing user-visible breaks.
 */

const ASSISTANT_DISCOVERED_STORAGE_KEY = "langflow-assistant-discovered";

export function readAssistantDiscovered(): boolean {
  try {
    return localStorage.getItem(ASSISTANT_DISCOVERED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function writeAssistantDiscovered(): void {
  try {
    localStorage.setItem(ASSISTANT_DISCOVERED_STORAGE_KEY, "true");
  } catch {
    // localStorage may be unavailable (private browsing) — silently ignore;
    // the worst case is the user sees the onboarding nudge again on next load.
  }
}
