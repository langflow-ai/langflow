import type { FlowType } from "@/types/flow";

interface IsFolderEmptyInput {
  flows: FlowType[] | undefined;
  folderId: string;
  folderTotal: number | undefined;
  enableMcp: boolean;
}

export function isFolderEmpty({
  flows,
  folderId,
  folderTotal,
  enableMcp,
}: IsFolderEmptyInput): boolean {
  // Two independent sources of truth for folder emptiness:
  //  - the global flows store (tab-agnostic, but can go stale after
  //    mutations if query invalidations miss it)
  //  - the current folder query total (fresh from the server, but
  //    filtered by the active tab)
  // Treat the folder as empty only when BOTH agree — this keeps the
  // tab-agnostic semantics while preventing a stale store from masking
  // a freshly moved flow in the destination project.
  const storeHasContent =
    flows?.some(
      (flow) =>
        flow.folder_id === folderId &&
        (enableMcp ? flow.is_component === false : true),
    ) ?? false;

  const queryHasContent = (folderTotal ?? 0) > 0;

  return !storeHasContent && !queryHasContent;
}
