import type { FlowType } from "@/types/flow";
import { addVersionToDuplicates } from "@/utils/reactflowUtils";

// Folder-scoped so a same-named flow in another folder never bumps this to "(1)".
export function getFolderScopedDuplicateName(
  flow: FlowType,
  flows: FlowType[],
  folderId?: string | null,
): string {
  const folderScopedFlows = flows.filter((f) => f.folder_id === folderId);
  return addVersionToDuplicates(flow, folderScopedFlows);
}
