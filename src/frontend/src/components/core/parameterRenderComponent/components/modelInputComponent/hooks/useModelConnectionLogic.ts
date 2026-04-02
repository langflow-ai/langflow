import { useCallback } from "react";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { groupByFamily } from "@/utils/utils";

interface UseModelConnectionLogicProps {
  nodeId: string;
  closePopover: () => void;
  clearSelection: () => void;
}

export function useModelConnectionLogic({
  nodeId,
  closePopover,
  clearSelection,
}: UseModelConnectionLogicProps) {
  const handleExternalOptions = useCallback(
    (optionValue: string) => {
      closePopover();
      clearSelection();

      if (optionValue !== "connect_other_models") {
        return;
      }

      try {
        const store = useFlowStore.getState();
        const node = store.getNode(nodeId!);
        const templateField = node?.data?.node?.template?.["model"];
        if (!templateField) {
          return;
        }

        const inputTypes: string[] =
          (Array.isArray(templateField.input_types)
            ? templateField.input_types
            : []) || [];
        const effectiveInputTypes =
          inputTypes.length > 0 ? inputTypes : ["LanguageModel"];

        const tooltipTitle: string =
          (inputTypes && inputTypes.length > 0
            ? inputTypes.join("\n")
            : templateField.type) || "";

        const typesData = useTypesStore.getState().data;
        const grouped = groupByFamily(
          typesData,
          (effectiveInputTypes && effectiveInputTypes.length > 0
            ? effectiveInputTypes.join("\n")
            : tooltipTitle) || "",
          true,
          store.nodes,
        );

        // Build a pseudo source so compatible target handles (left side) glow
        const pseudoSourceHandle = scapedJSONStringfy({
          fieldName: "model",
          id: nodeId,
          inputTypes: effectiveInputTypes,
          type: "str",
        });

        const filterObj = {
          source: undefined,
          sourceHandle: undefined,
          target: nodeId,
          targetHandle: pseudoSourceHandle,
          type: "LanguageModel",
          color: "datatype-fuchsia",
        } as any;

        // Mark this node as being in connection mode so the handle stays visible
        store.setNode(nodeId, (node) => ({
          ...node,
          data: { ...node.data, _connectionMode: true },
        }), false);

        // Show compatible handles glow
        store.setFilterEdge(grouped);
        store.setFilterType(filterObj);
      } catch (error) {
        console.warn("Error setting up connection mode:", error);
      }
    },
    [nodeId, closePopover, clearSelection],
  );

  return { handleExternalOptions };
}
