import { getApiKey } from "../../../../../controllers/API";
import { useTranslation } from "react-i18next";

const useApiKeys = (userData, setLoadingKeys, keysList, setUserId) => {
  const { t } = useTranslation();
  const fetchApiKeys = () => {
    setLoadingKeys(true);
    getApiKey()
      .then((keys) => {
        keysList.current = keys["api_keys"].map((apikey) => ({
          ...apikey,
          name: apikey.name && apikey.name !== "" ? apikey.name : t("Untitled"),
          last_used_at: apikey.last_used_at ?? t("Never"),
        }));
        setUserId(keys["user_id"]);
        setLoadingKeys(false);
      })
      .catch((error) => {
        setLoadingKeys(false);
      });
  };

  return {
    fetchApiKeys,
  };
};

export default useApiKeys;
