import {
  ERROR_UPDATING_COMPONENT,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "@/constants/constants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { ResponseErrorDetailAPI } from "@/types/api";
import { cloneDeep, debounce } from "lodash";
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

  const handleOnNewValue = async (newValue, dbValue?, skipSnapshot = false) => {
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

    if (JSON.stringify(parameter.value) === JSON.stringify(newValue)) return;

    if (!skipSnapshot) takeSnapshot();

    parameter.value = newValue;

    if (dbValue !== undefined) {
      parameter.load_from_db = dbValue;
    }

    const shouldUpdate =
      parameter.real_time_refresh && !parameter.refresh_button;

    if (shouldUpdate) {
      mutateTemplate(newValue, data, postTemplateValue, setNode, setErrorData);
    }

    setNode(data.id, (oldNode) => ({
      ...oldNode,
      data: cloneDeep(data),
    }));
  };

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
