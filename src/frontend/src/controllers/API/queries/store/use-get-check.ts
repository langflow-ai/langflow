import { useStoreStore } from "@/stores/storeStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type checkQueryResponse = {
  enabled: boolean;
};

export const useGetCheckQuery: useQueryFunctionType<
  undefined,
  checkQueryResponse
> = (_, options) => {
  const { query } = UseRequestProcessor();

  const getCheckFn = async () => {
    return await api.get<checkQueryResponse>(`${getURL("STORE")}/check/`);
  };

  const responseFn = async () => {
    const { data } = await getCheckFn();
    const setHasStore = useStoreStore.getState().checkHasStore;
    setHasStore(data);
    return data;
  };

  const queryResult = query(["useGetCheckQuery"], responseFn, { ...options });

  return queryResult;
};
