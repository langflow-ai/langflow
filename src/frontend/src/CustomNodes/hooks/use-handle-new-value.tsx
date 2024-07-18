import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { InputFieldType } from "@/types/api";
import { cloneDeep } from "lodash";
import { NodeDataType } from "../../types/flow";
import { mutateTemplate } from "../helpers/mutate-template";
const useHandleOnNewValue = ({
  data,
  name,
}: {
  data: NodeDataType;
  name: string;
}) => {
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const setNode = useFlowStore((state) => state.setNode);

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeData: data,
  });

  const handleOnNewValue = async (
    changes: Partial<InputFieldType>,
    options?: { skipSnapshot?: boolean },
  ) => {
    const template = data.node?.template;

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

    console.log(parameter);

    const shouldUpdate =
      parameter.real_time_refresh && !parameter.refresh_button;

    if (shouldUpdate && changes.value) {
      mutateTemplate(
        changes.value,
        data,
        postTemplateValue,
        setNode,
        setErrorData,
      );
    }

    setNode(data.id, (oldNode) => ({
      ...oldNode,
      data: cloneDeep(data),
    }));
  };

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
