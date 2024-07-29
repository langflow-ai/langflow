import useFlowStore from "@/stores/flowStore";
import { NodeType } from "@/types/flow";
import { cloneDeep } from "lodash";

const useHandleNodeClass = (
  nodeId: string,
  setMyNode?: (
    id: string,
    update: NodeType | ((oldState: NodeType) => NodeType),
  ) => void,
) => {
  const setNode = setMyNode ?? useFlowStore((state) => state.setNode);

  const handleNodeClass = (newNodeClass, type?: string) => {
    setNode(nodeId, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data = {
        ...newNode.data,
        node: cloneDeep(newNodeClass),
      };
      if (type) {
        newNode.data.type = type;
      }

      return newNode;
    });
  };

  return { handleNodeClass };
};

export default useHandleNodeClass;
