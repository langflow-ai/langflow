import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { CONTROL_PATCH_USER_STATE } from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import { usePostAddApiKey } from "@/controllers/API/queries/api-keys";
import useAlertStore from "@/stores/alertStore";
import { useStoreStore } from "@/stores/storeStore";
import { inputHandlerEventType } from "@/types/components";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import useScrollToElement from "../hooks/use-scroll-to-element";
import StoreApiKeyFormComponent from "./components/StoreApiKeyForm";

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
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start gap-6">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Langflow Store
            <ForwardedIconComponent
              name="Store"
              className="text-primary ml-2 h-5 w-5"
            />
          </h2>
          <p className="text-muted-foreground text-sm">
            Manage access to the Langflow Store.
          </p>
        </div>
      </div>
      <StoreApiKeyFormComponent
        apikey={inputState.apikey}
        handleInput={handleInput}
        handleSaveKey={handleSaveKey}
        loadingApiKey={loadingApiKey}
        validApiKey={validApiKey}
        hasApiKey={hasApiKey}
      />
    </div>
  );
};

export default StoreApiKeyPage;
