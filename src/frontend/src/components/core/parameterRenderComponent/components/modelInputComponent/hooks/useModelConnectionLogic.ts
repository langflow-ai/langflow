import { useCallback } from "react";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { groupByFamily } from "@/utils/utils";

interface UseModelConnectionLogicProps {
  nodeId: string;
  /** The model field entering connection mode. */
  fieldName: string;
  closePopover: () => void;
  clearSelection: () => void;
}

export function useModelConnectionLogic({
  nodeId,
  fieldName,
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
        const templateField = node?.data?.node?.template?.[fieldName];
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
          fieldName,
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
          // biome-ignore lint/suspicious/noExplicitAny: legacy
        } as any;

        // Mark this node as being in connection mode, clear the model value
        // and provider-specific credential fields so the backend cannot
        // execute with stale config when no external model is connected.
        store.setNode(
          nodeId,
          (prevNode) => {
            const template = { ...prevNode.data.node.template };
            if (template[fieldName]) {
              template[fieldName] = {
                ...template[fieldName],
                value: [],
                _connection_mode: true,
              };
            }
            for (const [key, field] of Object.entries(template)) {
              // biome-ignore lint/suspicious/noExplicitAny: legacy
              const f = field as any;
              if (f?.password || f?._input_type === "SecretStrInput") {
                template[key] = { ...f, value: "", load_from_db: false };
              }
            }
            return {
              ...prevNode,
              data: {
                ...prevNode.data,
                _connectionMode: true,
                node: { ...prevNode.data.node, template },
              },
            };
          },
          true,
        );

        // Show compatible handles glow
        store.setFilterEdge(grouped);
        store.setFilterType(filterObj);
      } catch (error) {
        console.warn("Error setting up connection mode:", error);
      }
    },
    [nodeId, fieldName, closePopover, clearSelection],
  );

  return { handleExternalOptions };
}
