import { cloneDeep } from "lodash";
import {
  ERROR_UPDATING_COMPONENT,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { ResponseErrorTypeAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";

const useHandleOnNewValue = (
  data: NodeDataType,
  name: string,
  takeSnapshot: () => void,
  handleUpdateValues: (name: string, data: NodeDataType) => Promise<any>,
  debouncedHandleUpdateValues: any,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
  setIsLoading: (value: boolean) => void,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleOnNewValue = async (newValue, dbValue, skipSnapshot = false) => {
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

      if (dbValue) {
        newNode.data.node.template[name].load_from_db = dbValue;
      }

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
