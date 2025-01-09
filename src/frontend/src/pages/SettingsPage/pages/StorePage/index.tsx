import { CONTROL_PATCH_USER_STATE } from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import { usePostAddApiKey } from "@/controllers/API/queries/api-keys";
import useAlertStore from "@/stores/alertStore";
import { useStoreStore } from "@/stores/storeStore";
import { inputHandlerEventType } from "@/types/components";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import StoreApiKeyFormComponent from "../StoreApiKeyPage/components/StoreApiKeyForm";
import useScrollToElement from "../hooks/use-scroll-to-element";

const StoreApiKeyPage = () => {
  const { scrollId } = useParams();
  const [inputState, setInputState] = useState(CONTROL_PATCH_USER_STATE);
  const { storeApiKey } = useContext(AuthContext);
  useScrollToElement(scrollId);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const {
    validApiKey,
    hasApiKey,
    loadingApiKey,
    updateHasApiKey: setHasApiKey,
    updateValidApiKey: setValidApiKey,
    updateLoadingApiKey: setLoadingApiKey,
  } = useStoreStore();

  const { mutate: addApiKey } = usePostAddApiKey({
    onSuccess: () => {
      setSuccessData({ title: "API key saved successfully" });
      setHasApiKey(true);
      setValidApiKey(true);
      setLoadingApiKey(false);
      handleInput({ target: { name: "apikey", value: "" } });
    },
    onError: (error) => {
      setErrorData({
        title: "API key save error",
        list: [(error as any)?.response?.data?.detail],
      });
      setHasApiKey(false);
      setValidApiKey(false);
      setLoadingApiKey(false);
    },
  });

  const handleSaveKey = (apikey: string) => {
    if (apikey) {
      addApiKey({ key: apikey });
      storeApiKey(apikey);
    }
  };

  const handleInput = ({ target: { name, value } }: inputHandlerEventType) => {
    setInputState((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <StoreApiKeyFormComponent
      apikey={inputState.apikey}
      handleInput={handleInput}
      handleSaveKey={handleSaveKey}
      loadingApiKey={loadingApiKey}
      validApiKey={validApiKey}
      hasApiKey={hasApiKey}
    />
  );
};

export default StoreApiKeyPage;
