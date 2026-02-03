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

function hasNodesAndEdges(obj: Record<string, unknown>): boolean {
  return (
    Array.isArray(obj.nodes) &&
    Array.isArray(obj.edges) &&
    (obj.nodes as unknown[]).length >= 0 &&
    (obj.edges as unknown[]).length >= 0
  );
}

function looksLikeFlowImportPayload(payload: unknown): boolean {
  if (!isRecord(payload)) return false;
  if (Array.isArray(payload.flows)) return true;
  if (isRecord(payload.data) && hasNodesAndEdges(payload.data)) return true;
  return hasNodesAndEdges(payload);
}

const JSON_MIME = "application/json";

function isFlowFile(file: File): boolean {
  return file.type === JSON_MIME || file.name.toLowerCase().endsWith(".json");
}

/**
 * Returns flow files from a paste event's clipboard (e.g. when user copies a .json file in the OS and pastes).
 * Normalizes type to application/json so upload flow accepts them. Returns empty array if none.
 *
 * @param dataTransfer - event.clipboardData from ClipboardEvent.
 */
export function getFlowFilesFromClipboard(dataTransfer: DataTransfer | null): File[] {
  if (!dataTransfer?.files?.length) return [];
  const out: File[] = [];
  for (let i = 0; i < dataTransfer.files.length; i++) {
    const file = dataTransfer.files[i];
    if (!isFlowFile(file)) continue;
    out.push(
      file.type === JSON_MIME ? file : new File([file], file.name, { type: JSON_MIME }),
    );
  }
  return out;
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
 * Normalizes payload so it has flow.data (nodes, edges). Accepts Langflow shape or raw { nodes, edges }.
 */
function normalizeToFlowShape(payload: Record<string, unknown>): Record<string, unknown> {
  if (Array.isArray(payload.flows)) return payload;
  if (isRecord(payload.data) && hasNodesAndEdges(payload.data)) return payload;
  if (hasNodesAndEdges(payload)) {
    return {
      ...payload,
      data: {
        nodes: payload.nodes,
        edges: payload.edges,
        viewport: (payload as { viewport?: unknown }).viewport ?? { x: 0, y: 0, zoom: 1 },
      },
    };
  }
  return payload;
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
  const normalized = normalizeToFlowShape(parsed as Record<string, unknown>);
  const safeTimestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return new File([JSON.stringify(normalized)], `pasted-flow-${safeTimestamp}.json`, {
    type: "application/json",
  });
}
