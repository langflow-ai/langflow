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

export function hasChatInputFiles(tweaks: Record<string, any>): boolean {
  return Object.values(tweaks).some(
    (tweak) =>
      tweak &&
      typeof tweak === "object" &&
      "files" in tweak &&
      typeof tweak.files === "string",
  );
}

export function getChatInputNodeId(tweaks: Record<string, any>): string | null {
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;
    
    if ("files" in tweak && typeof tweak.files === "string") {
      return nodeId;
    }
  }
  
  return null;
}

export function getFileNodeId(tweaks: Record<string, any>): string | null {
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") continue;
    
    // File component: { path: [...] }
    if ("path" in tweak && Array.isArray(tweak.path)) return nodeId;
    
    // Video File: { file_path: "..." }
    if ("file_path" in tweak && typeof tweak.file_path === "string") return nodeId;
  }
  
  return null;
}

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

export function getNonFileTypeTweaks(tweaks: Record<string, any>): Record<string, any> {
  const nonFileTweaks: Record<string, any> = {};
  for (const [nodeId, tweak] of Object.entries(tweaks)) {
    if (!tweak || typeof tweak !== "object") {
      nonFileTweaks[nodeId] = tweak;
      continue;
    }
    
    // Skip file-related tweaks
    const isFileComponent = ("path" in tweak && Array.isArray(tweak.path)) ||
                           ("file_path" in tweak && typeof tweak.file_path === "string") ||
                           ("files" in tweak && typeof tweak.files === "string");
    
    if (!isFileComponent) {
      nonFileTweaks[nodeId] = tweak;
    }
  }
  
  return nonFileTweaks;
}
