import { DEBOUNCE_FIELD_LIST } from "@/constants/constants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { APIClassType, InputFieldType } from "@/types/api";
import { AllNodeType } from "@/types/flow";
import { useUpdateNodeInternals } from "@xyflow/react";
import { cloneDeep, debounce } from "lodash";
import { useCallback, useMemo, useRef } from "react";
import { mutateTemplate } from "../helpers/mutate-template";

const DEBOUNCE_TIME_1_SECOND = 1000;

export type handleOnNewValueType = (
  changes: Partial<InputFieldType>,
  options?: {
    skipSnapshot?: boolean;
    setNodeClass?: (node: APIClassType) => void;
  },
) => void;

const useHandleOnNewValue = ({
  node,
  nodeId,
  name,
  setNode: setNodeExternal,
}: {
  node: APIClassType;
  nodeId: string;
  name: string;
  setNode?: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
  ) => void;
}) => {
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = setNodeExternal ?? useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Memoize the postTemplateValue hook to prevent unnecessary re-renders
  const postTemplateValue = usePostTemplateValue(
    useMemo(
      () => ({
        parameterId: name,
        nodeId,
        node,
        tool_mode: node.tool_mode ?? false,
      }),
      [name, nodeId, node, node.tool_mode],
    ),
  );

  // Memoize the node update function
  const updateNodeState = useCallback(
    (newNode: APIClassType) => {
      setNode(
        nodeId,
        (oldNode) => {
          const newData = cloneDeep(oldNode.data);
          newData.node = newNode;
          return {
            ...oldNode,
            data: newData,
          };
        },
        true,
        () => {
          updateNodeInternals(nodeId);
        },
      );
    },
    [nodeId, setNode, updateNodeInternals],
  );

  const debouncedMutateRef = useRef<any>(null);

  const handleOnNewValue: handleOnNewValueType = useCallback(
    async (changes, options?) => {
      const newNode = cloneDeep(node);
      const template = newNode.template;

      // Debounced tracking
      track("Component Edited", { nodeId });

      if (nodeId.toLowerCase().includes("astra") && name === "database_name") {
        track("Database Selected", { nodeId, databaseName: changes.value });
      }

      if (!template) {
        setErrorData({ title: "Template not found in the component" });
        return;
      }

      const parameter = template[name];

      if (!parameter) {
        setErrorData({ title: "Parameter not found in the template" });
        return;
      }

      const shouldDebounce = DEBOUNCE_FIELD_LIST.includes(
        parameter?._input_type,
      );

      if (!options?.skipSnapshot) takeSnapshot();

      Object.entries(changes).forEach(([key, value]) => {
        if (value !== undefined) parameter[key] = value;
      });

      const shouldUpdate = parameter.real_time_refresh;

      const setNodeClass = (newNodeClass: APIClassType) => {
        options?.setNodeClass?.(newNodeClass);
        updateNodeState(newNodeClass);
      };

      if (shouldUpdate && changes.value !== undefined) {
        if (!debouncedMutateRef.current) {
          debouncedMutateRef.current = debounce(
            async (
              value,
              node,
              setNodeClassFn,
              postTemplateFn,
              setErrorDataFn,
            ) => {
              await mutateTemplate(
                value,
                nodeId,
                node,
                setNodeClassFn,
                postTemplateFn,
                setErrorDataFn,
              );
            },
            shouldDebounce ? DEBOUNCE_TIME_1_SECOND : 0,
          );
        }
        debouncedMutateRef.current(
          changes.value,
          newNode,
          setNodeClass,
          postTemplateValue,
          setErrorData,
        );
      }

      updateNodeState(newNode);
    },
    [
      node,
      nodeId,
      name,
      takeSnapshot,
      postTemplateValue,
      setErrorData,
      updateNodeState,
    ],
  );

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
