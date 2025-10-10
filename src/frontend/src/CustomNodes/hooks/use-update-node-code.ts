import { cloneDeep } from "lodash"; // or any other deep cloning library you prefer
import { useCallback } from "react";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "../../types/api";
import { updateHiddenOutputs } from "../helpers/update-hidden-outputs";

const useUpdateNodeCode = (
  dataId: string,
  dataNode: APIClassType, // Define YourNodeType according to your data structure
  setNode: (id: string, callback: (oldNode) => any) => void,
  updateNodeInternals: (id: string) => void,
) => {
  const { setComponentsToUpdate } = useFlowStore();

  const updateNodeCode = useCallback(
    (newNodeClass: APIClassType, code: string, name: string, type: string) => {
      setNode(dataId, (oldNode) => {
        const newNode = cloneDeep(oldNode);

        newNode.data = {
          ...newNode.data,
          node: { ...newNodeClass, edited: false },
          description: newNodeClass.description ?? dataNode.description,
          display_name: newNodeClass.display_name ?? dataNode.display_name,
        };
        if (type) {
          newNode.data.type = type;
        }

        newNode.data.node.template[name].value = code;

        const outputs = dataNode.outputs;
        const updatedOutputs = newNodeClass.outputs;

        newNode.data.node!.outputs = updateHiddenOutputs(
          outputs!,
          updatedOutputs!,
        );

        return newNode;
      });

      setComponentsToUpdate((old) =>
        old.filter((component) => component.id !== dataId),
      );
      updateNodeInternals(dataId);
    },
    [dataId, dataNode, setNode, updateNodeInternals],
  );

  return updateNodeCode;
};

export default useUpdateNodeCode;
