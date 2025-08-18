/** Checks if the tweaks object contains any file-related fields (path for File, file_path for VideoFile, files for ChatInput). */
export function hasFileTweaks(tweaks: Record<string, any>): boolean {
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;

    // File component: { path: [...] }
    if ("path" in tweak && Array.isArray(tweak.path)) return true;

    // Video File: { file_path: "..." }
    if ("file_path" in tweak && typeof tweak.file_path === "string")
      return true;

    // Chat Input: { files: "..." } - files is a string field
    if ("files" in tweak && typeof tweak.files === "string") return true;
  }

  return false;
}

/** Checks specifically for ChatInput files field (v1 API). */
export function hasChatInputFiles(tweaks: Record<string, any>): boolean {
  return Object.values(tweaks).some(
    (tweak) =>
      tweak &&
      typeof tweak === "object" &&
      "files" in tweak &&
      typeof tweak.files === "string",
  );
}

/** Gets node ID for single ChatInput with files (v1). Returns null if none. */
export function getChatInputNodeId(tweaks: Record<string, any>): string | null {
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;

    if ("files" in tweak && typeof tweak.files === "string") {
      return nodeId;
    }
  }

  return null;
}

/** Gets node ID for single File/VideoFile (v2). Returns null if none. */
export function getFileNodeId(tweaks: Record<string, any>): string | null {
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;

    // File component: { path: [...] }
    if ("path" in tweak && Array.isArray(tweak.path)) return nodeId;

    // Video File: { file_path: "..." }
    if ("file_path" in tweak && typeof tweak.file_path === "string")
      return nodeId;
  }

  return null;
}

/** Gets all node IDs for ChatInputs with files (v1). */
export function getAllChatInputNodeIds(tweaks: Record<string, any>): string[] {
  const nodeIds: string[] = [];
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;

    if ("files" in tweak && typeof tweak.files === "string") {
      nodeIds.push(nodeId);
    }
  }

  return nodeIds;
}

/** Gets all node IDs for File/VideoFile components (v2). */
export function getAllFileNodeIds(tweaks: Record<string, any>): string[] {
  const nodeIds: string[] = [];
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;

    // File component: { path: [...] }
    if ("path" in tweak && Array.isArray(tweak.path)) {
      nodeIds.push(nodeId);
    }

    // Video File: { file_path: "..." }
    if ("file_path" in tweak && typeof tweak.file_path === "string") {
      nodeIds.push(nodeId);
    }
  }

  return nodeIds;
}

/** Filters out file-related tweaks, returning only non-file ones. */
export function getNonFileTypeTweaks(
  tweaks: Record<string, any>,
): Record<string, any> {
  const nonFileTweaks: Record<string, any> = {};
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") {
      nonFileTweaks[nodeId] = tweak;
      continue;
    }

    // Skip file-related tweaks
    const isFileComponent =
      ("path" in tweak && Array.isArray(tweak.path)) ||
      ("file_path" in tweak && typeof tweak.file_path === "string") ||
      ("files" in tweak && typeof tweak.files === "string");

    if (!isFileComponent) {
      nonFileTweaks[nodeId] = tweak;
    }
  }

  return nonFileTweaks;
}
