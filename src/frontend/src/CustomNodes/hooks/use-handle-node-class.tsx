import { cloneDeep } from "lodash";

const useHandleNodeClass = (
  takeSnapshot: () => void,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
  nodeId: string,
) => {
  const handleNodeClass = (newNodeClass, name, code, type?: string) => {
    if (code) {
      takeSnapshot();
    }

    setNode(nodeId, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data = {
        ...newNode.data,
        node: cloneDeep(newNodeClass),
      };
      if (type) {
        newNode.data.type = type;
      }
      if (code) {
        newNode.data.node.template[name].value = code;
      }

      return newNode;
    });
  };

  return { handleNodeClass };
};

export default useHandleNodeClass;
