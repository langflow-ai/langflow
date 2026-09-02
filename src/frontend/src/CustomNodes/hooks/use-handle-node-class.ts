import { useUpdateNodeInternals } from "@xyflow/react";
import { cloneDeep } from "lodash";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import type { FlowMutationOptions } from "@/types/zustand/flow";

const useHandleNodeClass = (
  nodeId: string,
  setMyNode?: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
    isUserChange?: boolean,
    callback?: () => void,
    options?: FlowMutationOptions,
  ) => void,
) => {
  const setNode = setMyNode ?? useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();

  const applyNodeClass = (
    newNodeClass,
    type?: string,
    options?: FlowMutationOptions,
  ) => {
    setNode(
      nodeId,
      (oldNode) => {
        const newNode = cloneDeep(oldNode);

        newNode.data = {
          ...newNode.data,
          node: cloneDeep(newNodeClass),
        };
        if (type) {
          newNode.data.type = type;
        }

        updateNodeInternals(nodeId);

        return newNode;
      },
      true,
      undefined,
      options,
    );
  };

  // Two parameters exactly: consumers pass this into props typed
  // `(value, code?, type?) => void`, where a third of another type breaks assignability.
  const handleNodeClass = (newNodeClass, type?: string) =>
    applyNodeClass(newNodeClass, type);

  // Catching up with the server is not the user's edit, so it must not save (#8995).
  const applyNodeClassFromRefresh = (newNodeClass, type?: string) =>
    applyNodeClass(newNodeClass, type, { autoSave: false });

  return { handleNodeClass, applyNodeClassFromRefresh };
};

export default useHandleNodeClass;
