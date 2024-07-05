import { getApiKey } from "../../../../../controllers/API";
import { Users } from "../../../../../types/api";

const useApiKeys = (
  userData: Users | null,
  setLoadingKeys: (load: boolean) => void,
  keysList: React.MutableRefObject<never[]>,
  setUserId: (userId: string) => void,
) => {
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
