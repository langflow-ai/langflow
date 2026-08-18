import type { FlowType } from "@/types/flow";
import { addVersionToDuplicates, type NamedFlow } from "@/utils/reactflowUtils";

// Folder scope matches the UI grouping; user scope matches the DB's unique (user_id, name).
export function getFolderScopedDuplicateName(
  flow: FlowType,
  flows: FlowType[],
  folderId?: string | null,
): string {
  const folderScopedFlows = flows.filter((f) => f.folder_id === folderId);
  return addVersionToDuplicates(flow, folderScopedFlows);
}

export function getUserScopedDuplicateName(
  flow: FlowType,
  flows: NamedFlow[],
  ownerlessExamples: Pick<FlowType, "id">[] = [],
): string {
  const ownerlessExampleIds = new Set(
    ownerlessExamples.map((example) => example.id),
  );
  return addVersionToDuplicates(
    flow,
    flows.filter((f) => !ownerlessExampleIds.has(f.id)),
  );
}
