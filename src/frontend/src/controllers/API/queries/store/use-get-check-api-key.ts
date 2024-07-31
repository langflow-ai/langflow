import { useStoreStore } from "@/stores/storeStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ICheckQueryResponse {
  has_api_key: boolean;
  is_valid: boolean;
}

export const useGetCheckApiKeysQuery: useQueryFunctionType<
  undefined,
  ICheckQueryResponse
> = (_, options) => {
  const { query } = UseRequestProcessor();

  const getCheckFn = async () => {
    return await api.get<ICheckQueryResponse>(
      `${getURL("STORE")}/check/api_key`,
    );
  };

  const responseFn = async () => {
    const { data } = await getCheckFn();
    const { fetchApiData } = useStoreStore.getState();
    fetchApiData(data);
    return data;
  };

  const queryResult = query(["useGetCheckApiKeysQuery"], responseFn, {
    ...options,
  });

  return queryResult;
};
