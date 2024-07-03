import { useContext } from "react";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import { useStoreStore } from "../../../../stores/storeStore";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddApiKey {
  key: string;
}

interface UsePostAddApiKeyParams {
  callbackSuccess?: () => void;
  callbackError?: () => void;
}

export function usePostAddApiKey({
  callbackSuccess = () => {},
  callbackError = () => {},
}: UsePostAddApiKeyParams) {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { storeApiKey } = useContext(AuthContext);
  const setHasApiKey = useStoreStore((state) => state.updateHasApiKey);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const setLoadingApiKey = useStoreStore((state) => state.updateLoadingApiKey);

  const { mutate } = UseRequestProcessor();

  const postAddApiKeyFn = async (payload: IPostAddApiKey) => {
    return await api.post<any>(`${getURL("API_KEY")}/store`, {
      api_key: payload.key,
    });
  };

  const mutation = mutate(
    ["usePostAddApiKey"],
    async (payload: IPostAddApiKey) => {
      const res = await postAddApiKeyFn(payload);
      return res.data;
    },
    {
      onError: () => {
        setErrorData({
          title: "API key save error",
          list: [(mutation.error as any)?.response?.data?.detail],
        });
        setHasApiKey(false);
        setValidApiKey(false);
        setLoadingApiKey(false);
        if (callbackError) {
          callbackError();
        }
      },
      onSuccess: (data) => {
        setSuccessData({ title: "API key saved successfully" });
        storeApiKey(data);
        setHasApiKey(true);
        setValidApiKey(true);
        setLoadingApiKey(false);
        if (callbackSuccess) {
          callbackSuccess();
        }
      },
    },
  );

  return mutation;
}
