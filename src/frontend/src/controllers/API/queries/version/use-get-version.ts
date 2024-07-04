import { useDarkStore } from "@/stores/darkStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface versionQueryResponse {
  version: string;
  package: string;
}

export const useGetVersionQuery: useQueryFunctionType<
  undefined,
  versionQueryResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const { data } = await getVersionFn();
    const refreshVersion = useDarkStore.getState().refreshVersion;
    return refreshVersion(data.version);
  };

  const getVersionFn = async () => {
    return await api.get<versionQueryResponse>(`${getURL("VERSION")}`);
  };

  const queryResult = query(["useGetVersionQuery"], responseFn, { ...options });

  return queryResult;
};
