/**
 * Shared helpers for importing flow JSON from clipboard (paste).
 * Used by MainPage (new flow) and FlowPage (paste into current flow).
 */

/** Max clipboard length to parse; avoids DoS from huge pastes. */
const MAX_PASTE_LENGTH = 5_000_000;

function stripJsonCodeFence(text: string): string {
  const trimmed = text.trim();
  return trimmed
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function looksLikeFlowImportPayload(payload: unknown): boolean {
  if (!isRecord(payload)) return false;
  if (Array.isArray(payload.flows)) return true;
  if (!isRecord(payload.data)) return false;
  return (
    Array.isArray(payload.data.nodes) && Array.isArray(payload.data.edges)
  );
}

/**
 * Returns true when paste should not be hijacked (user is typing in an input/editor).
 *
 * @param target - The event target of the paste (e.g. event.target).
 */
export function isEditablePasteTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target.isContentEditable === true
  );
}

/**
 * If clipboard text is valid flow/collection JSON, returns a File suitable for useUploadFlow.
 * Otherwise returns null. Rejects empty or oversized input.
 *
 * @param text - Raw clipboard text (e.g. from clipboardData.getData("text/plain")).
 */
export function getPastedFlowFile(text: string): File | null {
  if (!text || text.length > MAX_PASTE_LENGTH) return null;
  const maybeJson = stripJsonCodeFence(text);
  if (!maybeJson) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(maybeJson);
  } catch {
    return null;
  }
  if (!looksLikeFlowImportPayload(parsed)) return null;
  const safeTimestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return new File([JSON.stringify(parsed)], `pasted-flow-${safeTimestamp}.json`, {
    type: "application/json",
  });
}
