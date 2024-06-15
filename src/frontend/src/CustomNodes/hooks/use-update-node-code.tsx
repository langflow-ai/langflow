import { cloneDeep } from "lodash"; // or any other deep cloning library you prefer
import { useCallback } from "react";
import { APIClassType } from "../../types/api";

const useUpdateNodeCode = (
  dataId: string,
  dataNode: APIClassType, // Define YourNodeType according to your data structure
  setNode: (id: string, callback: (oldNode) => any) => void,
  setIsOutdated: (value: boolean) => void,
  updateNodeInternals: (id: string) => void,
) => {
  const updateNodeCode = useCallback(
    (newNodeClass: APIClassType, code: string, name: string) => {
      setNode(dataId, (oldNode) => {
        let newNode = cloneDeep(oldNode);

        newNode.data = {
          ...newNode.data,
          node: newNodeClass,
          description: newNodeClass.description ?? dataNode.description,
          display_name: newNodeClass.display_name ?? dataNode.display_name,
          edited: false,
        };

        newNode.data.node.template[name].value = code;
        setIsOutdated(false);

        return newNode;
      });

      updateNodeInternals(dataId);
    },
    [dataId, dataNode, setNode, setIsOutdated, updateNodeInternals],
  );

  return updateNodeCode;
};

export default useUpdateNodeCode;
