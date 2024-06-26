import {
  DEL_KEY_ERROR_ALERT,
  DEL_KEY_ERROR_ALERT_PLURAL,
  DEL_KEY_SUCCESS_ALERT,
  DEL_KEY_SUCCESS_ALERT_PLURAL,
} from "../../../../../constants/alerts_constants";
import { deleteApiKey } from "../../../../../controllers/API";
import { useTranslation } from "react-i18next";

const useDeleteApiKeys = (
  selectedRows: string[],
  resetFilter: () => void,
  setSuccessData: (data: { title: string }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
) => {
  const { t } = useTranslation();
  const handleDeleteKey = () => {
    Promise.all(selectedRows.map((selectedRow) => deleteApiKey(selectedRow)))
      .then(() => {
        resetFilter();
        setSuccessData({
          title:
            selectedRows.length === 1
              ? t(DEL_KEY_SUCCESS_ALERT)
              : t(DEL_KEY_SUCCESS_ALERT_PLURAL),
        });
      })
      .catch((error) => {
        setErrorData({
          title:
            selectedRows.length === 1
              ? t(DEL_KEY_ERROR_ALERT)
              : t(DEL_KEY_ERROR_ALERT_PLURAL),
          list: [error?.response?.data?.detail],
        });
      });
  };

  return {
    handleDeleteKey,
  };
};

export default useDeleteApiKeys;
