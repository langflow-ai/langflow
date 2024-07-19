import useFlowStore from "@/stores/flowStore";
import { cloneDeep } from "lodash";

const useHandleNodeClass = (nodeId: string) => {
  const setNode = useFlowStore((state) => state.setNode);

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
