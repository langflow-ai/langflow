import type {
  ToolExport,
  ToolPackBinding,
  ToolPackReference,
} from "@/controllers/API/queries/folders/use-project-tool-pack";
import type { FlowType } from "@/types/flow";

export const packProjectPath = (projectId: string, harnessId?: string) =>
  `/all/folder/${encodeURIComponent(projectId)}?tab=harness${harnessId ? `&fromHarness=${encodeURIComponent(harnessId)}` : ""}`;

export function selectedToolPacks(value: unknown): ToolPackReference[] {
  return Array.isArray(value) ? value : [];
}

/** Only use canvas exports whose reference is the revision being reviewed. */
export function appliedPackTools(
  flow: FlowType | undefined,
  reference: ToolPackReference,
): ToolExport[] | undefined {
  const bindings = (flow?.data?.nodes ?? []).flatMap((node) => {
    const origin = (
      node.data as { _harness_tool?: { tool_pack?: ToolPackBinding } }
    )._harness_tool;
    const binding = origin?.tool_pack;
    return binding?.reference.project_id === reference.project_id &&
      binding.reference.revision === reference.revision
      ? [binding]
      : [];
  });
  return bindings.length ? bindings.map((binding) => binding.tool) : undefined;
}

export function exportChanges(
  previous: ToolExport[] | undefined,
  current: ToolExport[],
) {
  const old = new Map(previous?.map((tool) => [tool.flow_id, tool]));
  const next = new Set(current.map((tool) => tool.flow_id));
  return [
    ...current.map((tool) => {
      const before = old.get(tool.flow_id);
      const status = !previous
        ? undefined
        : !before
          ? "added"
          : before.revision !== tool.revision ||
              before.name !== tool.name ||
              before.description !== tool.description
            ? "updated"
            : "unchanged";
      return { tool, before, status };
    }),
    ...(previous ?? [])
      .filter((tool) => !next.has(tool.flow_id))
      .map((tool) => ({ tool, before: tool, status: "removed" })),
  ];
}
