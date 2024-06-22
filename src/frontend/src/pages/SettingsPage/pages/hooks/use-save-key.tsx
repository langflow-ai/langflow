import { useContext } from "react";
import {
  API_ERROR_ALERT,
  API_SUCCESS_ALERT,
} from "../../../../constants/alerts_constants";
import { AuthContext } from "../../../../contexts/authContext";
import { addApiKeyStore } from "../../../../controllers/API";

const useSaveKey = (
  setSuccessData,
  setErrorData,
  setHasApiKey,
  setValidApiKey,
  setLoadingApiKey,
) => {
  const { storeApiKey } = useContext(AuthContext);

  const handleSaveKey = (apikey, handleInput) => {
    if (apikey) {
      setLoadingApiKey(true);
      addApiKeyStore(apikey).then(
        () => {
          setSuccessData({ title: API_SUCCESS_ALERT });
          storeApiKey(apikey);
          setHasApiKey(true);
          setValidApiKey(true);
          setLoadingApiKey(false);
          handleInput({ target: { name: "apikey", value: "" } });
        },
        (error) => {
          setErrorData({
            title: API_ERROR_ALERT,
            list: [error.response.data.detail],
          });
          setHasApiKey(false);
          setValidApiKey(false);
          setLoadingApiKey(false);
        },
      );
    }
  };

  return {
    handleSaveKey,
  };
};

export default useSaveKey;
