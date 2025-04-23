import { useDarkStore } from "@/stores/darkStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface versionQueryResponse {
  version: string;
  package: string;
  main_version: string;
}

export const useGetVersionQuery: useQueryFunctionType<
  undefined,
  versionQueryResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getVersionFn = async () => {
    return await api.get<versionQueryResponse>(`${getURL("VERSION")}`);
  };

  const responseFn = async () => {
    const { data } = await getVersionFn();
    const refreshVersion = useDarkStore.getState().refreshVersion;
    const refreshLatestVersion = useDarkStore.getState().refreshLatestVersion;
    refreshVersion(data.version);
    refreshLatestVersion(data.main_version);
    return data;
  };

  const queryResult = query(["useGetVersionQuery"], responseFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
