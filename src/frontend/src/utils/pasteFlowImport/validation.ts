/**
 * Validation helpers for flow paste processing.
 * Used by parsing.ts and re-exported for consumers.
 */

export const JSON_MIME = "application/json";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function hasNodesAndEdges(obj: Record<string, unknown>): boolean {
  return (
    Array.isArray(obj.nodes) &&
    Array.isArray(obj.edges) &&
    (obj.nodes as unknown[]).length >= 0 &&
    (obj.edges as unknown[]).length >= 0
  );
}

export function looksLikeFlowImportPayload(payload: unknown): boolean {
  if (!isRecord(payload)) return false;
  if (Array.isArray(payload.flows)) return true;
  if (isRecord(payload.data) && hasNodesAndEdges(payload.data)) return true;
  return hasNodesAndEdges(payload);
}

export function isFlowFile(file: File): boolean {
  return file.type === JSON_MIME || file.name.toLowerCase().endsWith(".json");
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
