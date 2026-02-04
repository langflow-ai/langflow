/**
 * Parsing and extraction helpers for flow paste processing.
 * Consumes validation helpers and exposes getPastedFlowFile / getFlowFilesFromClipboard.
 */

import {
  hasNodesAndEdges,
  isFlowFile,
  isRecord,
  JSON_MIME,
  looksLikeFlowImportPayload,
} from "./validation";

/** Max clipboard length to parse; avoids DoS from huge pastes. */
const MAX_PASTE_LENGTH = 5_000_000;

function stripJsonCodeFence(text: string): string {
  const trimmed = text.trim();
  return trimmed
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

/**
 * Normalizes payload so it has flow.data (nodes, edges). Accepts Langflow shape or raw { nodes, edges }.
 */
function normalizeToFlowShape(
  payload: Record<string, unknown>,
): Record<string, unknown> {
  if (Array.isArray(payload.flows)) return payload;
  if (isRecord(payload.data) && hasNodesAndEdges(payload.data)) return payload;
  if (hasNodesAndEdges(payload)) {
    return {
      ...payload,
      data: {
        nodes: payload.nodes,
        edges: payload.edges,
        viewport: (payload as { viewport?: unknown }).viewport ?? {
          x: 0,
          y: 0,
          zoom: 1,
        },
      },
    };
  }
  return payload;
}

/**
 * Returns flow files from a paste event's clipboard (e.g. when user copies a .json file in the OS and pastes).
 * Normalizes type to application/json so upload flow accepts them. Returns empty array if none.
 *
 * @param dataTransfer - event.clipboardData from ClipboardEvent.
 */
export function getFlowFilesFromClipboard(
  dataTransfer: DataTransfer | null,
): File[] {
  if (!dataTransfer?.files?.length) return [];
  const out: File[] = [];
  for (let i = 0; i < dataTransfer.files.length; i++) {
    const file = dataTransfer.files[i];
    if (!isFlowFile(file)) continue;
    out.push(
      file.type === JSON_MIME
        ? file
        : new File([file], file.name, { type: JSON_MIME }),
    );
  }
  return out;
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
  return new File(
    [JSON.stringify(normalized)],
    `pasted-flow-${safeTimestamp}.json`,
    {
      type: "application/json",
    },
  );
}
