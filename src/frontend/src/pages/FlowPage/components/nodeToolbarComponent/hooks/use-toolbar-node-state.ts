import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { NodeDataType } from "@/types/flow";
import { checkHasToolMode } from "@/utils/reactflowUtils";
import { getNodeLength } from "@/utils/utils";

export interface UseToolbarNodeStateParams {
  data: NodeDataType;
  allowCustomComponents: boolean;
  isPostToolModePending: boolean;
}

export interface UseToolbarNodeStateResult {
  nodeLength: number;
  hasCode: boolean;
  canEditCode: boolean;
  isGroup: boolean;
  hasToolMode: boolean;
  toolMode: boolean;
  setToolMode: Dispatch<SetStateAction<boolean>>;
}

/**
 * Derives the toolbar's node-shape state (length, code/group/tool-mode flags)
 * and owns the optimistic tool-mode toggle synced from the rebuilt node.
 * Extracted verbatim from NodeToolbarComponent (LE-1736 W28).
 */
export function useToolbarNodeState({
  data,
  allowCustomComponents,
  isPostToolModePending,
}: UseToolbarNodeStateParams): UseToolbarNodeStateResult {
  const nodeLength = useMemo(() => getNodeLength(data), [data]);
  const hasCode = useMemo(
    () => Object.keys(data.node!.template).includes("code"),
    [data.node],
  );
  const canEditCode = hasCode && allowCustomComponents;
  const isGroup = useMemo(() => (data.node?.flow ? true : false), [data.node]);

  const hasToolMode = useMemo(
    () => checkHasToolMode(data.node?.template ?? {}) && !isGroup,
    [data.node?.template, isGroup],
  );

  const [toolMode, setToolMode] = useState(
    () =>
      data.node?.tool_mode ||
      data.node?.outputs?.some(
        (output) => output.name === "component_as_tool",
      ) ||
      false,
  );

  useEffect(() => {
    // Keep the optimistic toggle state while the server rebuilds the node.
    // Other in-flight field refreshes can update the same node first with
    // its previous tool_mode value; syncing that transient value makes the
    // toggle appear to turn itself off.
    if (isPostToolModePending) return;

    if (data.node?.tool_mode !== undefined) {
      setToolMode(
        data.node?.tool_mode ||
          data.node?.outputs?.some(
            (output) => output.name === "component_as_tool",
          ) ||
          false,
      );
    }
  }, [data.node?.tool_mode, data.node?.outputs, isPostToolModePending]);

  return {
    nodeLength,
    hasCode,
    canEditCode,
    isGroup,
    hasToolMode,
    toolMode,
    setToolMode,
  };
}
