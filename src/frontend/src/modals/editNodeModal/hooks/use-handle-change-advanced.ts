import { cloneDeep } from "lodash";
import { NodeDataType } from "../../../types/flow";

const useHandleChangeAdvanced = (
  data: NodeDataType,
  takeSnapshot: () => void,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
  updateNodeInternals: (id: string) => void,
) => {
  const handleChangeAdvanced = (name) => {
    if (!data.node) return;
    takeSnapshot();

    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data.node.template[name].advanced =
        !newNode.data.node.template[name].advanced;

      return newNode;
    });

    updateNodeInternals(data.id);
  };

  return { handleChangeAdvanced };
};

export default useHandleChangeAdvanced;
