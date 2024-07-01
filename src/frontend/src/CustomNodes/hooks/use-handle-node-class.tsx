import { cloneDeep } from "lodash";
import { NodeDataType } from "../../types/flow";

const useHandleNodeClass = (
  data: NodeDataType,
  name: string,
  takeSnapshot: () => void,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
  updateNodeInternals: (id: string) => void,
) => {
  const handleNodeClass = (newNodeClass, code, type?: string) => {
    if (!data.node) return;
    if (data.node!.template[name].value !== code) {
      takeSnapshot();
    }

    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data = {
        ...newNode.data,
        node: newNodeClass,
        description: newNodeClass.description ?? data.node!.description,
        display_name: newNodeClass.display_name ?? data.node!.display_name,
      };
      if (type) {
        newNode.data.node.template[name].type = type;
      }
      newNode.data.node.template[name].value = code;

      return newNode;
    });

    updateNodeInternals(data.id);
  };

  return { handleNodeClass };
};

export default useHandleNodeClass;
