import type { FlowType } from "@/types/flow";
import type { FolderType } from "../entities";

export function shouldShowMainContent(
  flows: FlowType[] | undefined,
  examples: FlowType[] | undefined,
  folders: FolderType[] | undefined,
): boolean {
  if (!flows || !examples || !folders) return false;
  const exampleIds = new Set(examples.map((example) => example.id));
  const userOwnedFlows = flows.filter((flow) => !exampleIds.has(flow.id));
  return userOwnedFlows.length > 0 || folders.length > 1;
}
