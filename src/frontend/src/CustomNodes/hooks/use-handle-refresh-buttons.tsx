import { cloneDeep } from "lodash";
import {
  ERROR_UPDATING_COMPONENT,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { ResponseErrorDetailAPI } from "../../types/api";
import { handleUpdateValues } from "../../utils/parameterUtils";
import { useTranslation } from "react-i18next";

const useHandleRefreshButtonPress = (
  setIsLoading: (value: boolean) => void,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
) => {

  const { t } = useTranslation();

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
        title: t(TITLE_ERROR_UPDATING_COMPONENT),
        list: [
          responseError?.response?.data?.detail ?? t(ERROR_UPDATING_COMPONENT),
        ],
      });
    }
    setIsLoading(false);
  };

  return { handleRefreshButtonPress };
};

export default useHandleRefreshButtonPress;
