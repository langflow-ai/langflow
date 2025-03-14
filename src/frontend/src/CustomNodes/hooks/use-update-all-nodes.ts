import { AllNodeType } from "@/types/flow";
import { cloneDeep } from "lodash";
import { useCallback } from "react";
import { APIClassType, OutputFieldType } from "../../types/api";
import { updateHiddenOutputs } from "../helpers/update-hidden-outputs";

export type UpdateNodesType = {
  nodeId: string;
  newNode: APIClassType;
  code: string;
  name: string;
  type?: string;
};

const useUpdateAllNodes = (
  setNodes: (
    update: AllNodeType[] | ((oldState: AllNodeType[]) => AllNodeType[]),
  ) => void,
  updateNodeInternals: (nodeId: string) => void,
) => {
  const updateAllNodes = useCallback(
    (updates: UpdateNodesType[]) => {
      setNodes((oldNodes) => {
        const newNodes = cloneDeep(oldNodes);

        updates.forEach(({ nodeId, newNode, code, name, type }) => {
          const nodeIndex = newNodes.findIndex((n) => n.id === nodeId);
          if (nodeIndex === -1) return;

          const updatedNode = newNodes[nodeIndex];
          const outputs = updatedNode?.data.node?.outputs;

          updatedNode.data = {
            ...updatedNode.data,
            node: {
              ...newNode,
              description:
                newNode.description ?? updatedNode.data.node?.description,
              display_name:
                newNode.display_name ?? updatedNode.data.node?.display_name,
              edited: false,
            },
          };

          if (type) {
            updatedNode.data.type = type;
          }

          updatedNode.data.node!.template[name].value = code;

          const updatedOutputs = updatedNode.data.node?.outputs;
          updatedNode.data.node!.outputs = updateHiddenOutputs(
            outputs!,
            updatedOutputs!,
          );

          updateNodeInternals(nodeId);
        });

        return newNodes;
      });
    },
    [setNodes, updateNodeInternals],
  );

  return updateAllNodes;
};

export default useUpdateAllNodes;
