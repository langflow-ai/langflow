import { cloneDeep } from "lodash";
import useAlertStore from "../../stores/alertStore";
import { ResponseErrorDetailAPI } from "../../types/api";
import { handleUpdateValues } from "../../utils/parameterUtils";

const useHandleRefreshButtonPress = (setIsLoading, setNode, renderTooltips) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleRefreshButtonPress = async (name, data) => {
    setIsLoading(true);
    try {
      let newTemplate = await handleUpdateValues(name, data);

      if (newTemplate) {
        setNode(data.id, (oldNode) => {
          let newNode = cloneDeep(oldNode);
          newNode.data = {
            ...newNode.data,
          };
          newNode.data.node.template = newTemplate;
          return newNode;
        });
      }
    } catch (error) {
      let responseError = error as ResponseErrorDetailAPI;

      setErrorData({
        title: "Error while updating the Component",
        list: [responseError?.response?.data?.detail ?? "Unknown error"],
      });
    }
    setIsLoading(false);
    renderTooltips();
  };

  return { handleRefreshButtonPress };
};

export default useHandleRefreshButtonPress;
