import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { APIClassType, InputFieldType } from "@/types/api";
import { cloneDeep } from "lodash";
import { mutateTemplate } from "../helpers/mutate-template";
const useHandleOnNewValue = ({
  node,
  nodeId,
  name,
}: {
  node: APIClassType;
  nodeId: string;
  name: string;
}) => {
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const setNode = useFlowStore((state) => state.setNode);

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: node,
  });

  const handleOnNewValue = async (
    changes: Partial<InputFieldType>,
    options?: { skipSnapshot?: boolean },
  ) => {
    const newNode = cloneDeep(node);
    const template = newNode.template;

    if (!template) {
      setErrorData({ title: "Template not found in the component" });
      return;
    }

    const parameter = template[name];

    if (!parameter) {
      setErrorData({ title: "Parameter not found in the template" });
      return;
    }

    if (!options?.skipSnapshot) takeSnapshot();

    Object.entries(changes).forEach(([key, value]) => {
      parameter[key] = value;
    });

    const shouldUpdate =
      parameter.real_time_refresh && !parameter.refresh_button;

    if (shouldUpdate && changes.value) {
      mutateTemplate(
        changes.value,
        newNode,
        nodeId,
        postTemplateValue,
        setNode,
        setErrorData,
      );
    }

    setNode(nodeId, (oldNode) => {
      const newData = cloneDeep(oldNode.data);
      newData.node = newNode;
      return {
        ...oldNode,
        data: newData,
      };
    });
  };

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
