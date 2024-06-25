import { cloneDeep } from "lodash";
import { Node } from "reactflow";
import {
  ERROR_UPDATING_COMPONENT,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { APITemplateType, ResponseErrorTypeAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";

type debounce = {};

const useHandleOnNewValue = (
  data: NodeDataType,
  name: string,
  takeSnapshot: () => void,
  handleUpdateValues: (
    name: string,
    data: NodeDataType,
  ) => Promise<APITemplateType | void>,
  debouncedHandleUpdateValues: (name: string, data: NodeDataType) => void,
  setNode: (id: string, update: Node | ((oldState: Node) => Node)) => void,
  setIsLoading: (loading: boolean | ((old: boolean) => boolean)) => void,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleOnNewValue = async (newValue, skipSnapshot = false) => {
    const nodeTemplate = data.node!.template[name];
    const currentValue = nodeTemplate.value;

    if (currentValue !== newValue && !skipSnapshot) {
      takeSnapshot();
    }

    const shouldUpdate =
      data.node?.template[name].real_time_refresh &&
      !data.node?.template[name].refresh_button &&
      currentValue !== newValue;

    const typeToDebounce = nodeTemplate.type;

    nodeTemplate.value = newValue;

    let newTemplate;
    if (shouldUpdate) {
      setIsLoading(true);
      try {
        if (["int"].includes(typeToDebounce)) {
          newTemplate = await handleUpdateValues(name, data);
        } else {
          newTemplate = await debouncedHandleUpdateValues(name, data);
        }
      } catch (error) {
        let responseError = error as ResponseErrorTypeAPI;
        setErrorData({
          title: TITLE_ERROR_UPDATING_COMPONENT,
          list: [
            responseError?.response?.data?.detail.error ??
              ERROR_UPDATING_COMPONENT,
          ],
        });
      }
      setIsLoading(false);
    }

    setNode(data.id, (oldNode) => {
      const newNode = cloneDeep(oldNode);
      newNode.data = {
        ...newNode.data,
      };

      if (data.node?.template[name].real_time_refresh && newTemplate) {
        newNode.data.node.template = newTemplate;
      } else {
        newNode.data.node.template[name].value = newValue;
      }

      return newNode;
    });
  };

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
