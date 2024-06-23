import { getApiKey } from "../../../../../controllers/API";

const useApiKeys = (userData, setLoadingKeys, keysList, setUserId) => {
  const fetchApiKeys = () => {
    setLoadingKeys(true);
    getApiKey()
      .then((keys) => {
        keysList.current = keys["api_keys"].map((apikey) => ({
          ...apikey,
          name: apikey.name && apikey.name !== "" ? apikey.name : "Untitled",
          last_used_at: apikey.last_used_at ?? "Never",
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
