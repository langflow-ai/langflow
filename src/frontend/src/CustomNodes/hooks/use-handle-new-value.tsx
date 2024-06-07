import { cloneDeep } from "lodash";
import useAlertStore from "../../stores/alertStore";
import { ResponseErrorTypeAPI } from "../../types/api";

const useHandleOnNewValue = (
  data,
  name,
  takeSnapshot,
  handleUpdateValues,
  debouncedHandleUpdateValues,
  setNode,
  renderTooltips,
  setIsLoading,
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
          title: "Error while updating the Component",
          list: [
            responseError?.response?.data?.detail.error ?? "Unknown error",
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

    renderTooltips();
  };

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
