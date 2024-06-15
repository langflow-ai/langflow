import { cloneDeep } from "lodash";

const useHandleNodeClass = (
  data,
  name,
  takeSnapshot,
  setNode,
  updateNodeInternals,
  renderTooltips,
) => {
  const handleNodeClass = (newNodeClass, code) => {
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

      newNode.data.node.template[name].value = code;

      return newNode;
    });

    updateNodeInternals(data.id);

    renderTooltips();
  };

  return { handleNodeClass };
};

export default useHandleNodeClass;
