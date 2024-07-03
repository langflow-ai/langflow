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
  callbackSuccess?: (data) => void;
  callbackError?: (err) => void;
}

export const usePostAddApiKey = ({
  callbackSuccess = () => {},
  callbackError = () => {},
}: UsePostAddApiKeyParams) => {
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
      onError: (err) => {
        if (callbackError) {
          callbackError(err);
        }
      },
      onSuccess: (data) => {
        if (callbackSuccess) {
          callbackSuccess(data);
        }
      },
    },
  );

  return mutation;
};
