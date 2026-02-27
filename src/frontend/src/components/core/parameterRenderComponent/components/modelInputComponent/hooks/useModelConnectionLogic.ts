import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { groupByFamily } from "@/utils/utils";
import { useCallback } from "react";

interface UseModelConnectionLogicProps {
  nodeId: string;
  nodeClass: any;
  handleNodeClass: (nodeClass: any) => void;
  postTemplateValue: any;
  setErrorData: (error: any) => void;
  handleOnNewValue: (newValue: any) => void;
  closePopover: () => void;
  clearSelection: () => void;
}

export function useModelConnectionLogic({
  nodeId,
  nodeClass,
  handleNodeClass,
  postTemplateValue,
  setErrorData,
  handleOnNewValue,
  closePopover,
  clearSelection,
}: UseModelConnectionLogicProps) {
  const handleExternalOptions = useCallback(
    async (optionValue: string) => {
      closePopover();
      clearSelection();

      // Pass the optionValue ("connect_other_models") as both the field value and to mutateTemplate
      // This way the backend knows we're in connection mode
      handleOnNewValue({ value: optionValue });

      await mutateTemplate(
        optionValue,
        nodeId!,
        nodeClass!,
        handleNodeClass!,
        postTemplateValue,
        setErrorData,
        "model",
        () => {
          // Enable connection mode for connect_other_models AFTER mutation completes
          try {
            if (optionValue === "connect_other_models") {
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

              const myId = scapedJSONStringfy({
                inputTypes: effectiveInputTypes,
                type: templateField.type,
                id: nodeId,
                fieldName: "model",
                proxy: templateField.proxy,
              });

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

              // Show compatible handles glow
              store.setFilterEdge(grouped);
              store.setFilterType(filterObj);
            }
          } catch (error) {
            console.warn("Error setting up connection mode:", error);
          }
        },
      );
    },
    [
      nodeId,
      nodeClass,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
      handleOnNewValue,
      closePopover,
      clearSelection,
    ],
  );

  return { handleExternalOptions };
}
