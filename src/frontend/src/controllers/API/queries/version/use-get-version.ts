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
> = (_, onFetch) => {
  const { query } = UseRequestProcessor();

  const responseFn = (data: versionQueryResponse) => {
    if (!onFetch) return data;
    if (typeof onFetch === "function") return onFetch(data);
    const refreshVersion = useDarkStore.getState().refreshVersion;
    switch (onFetch) {
      case "updateState": {
        return refreshVersion(data.version);
      }
      default:
        return data;
    }
  };

  const getVersionFn = async () => {
    return await api.get<versionQueryResponse>(`${getURL("VERSION")}`);
  };

  const queryResult = query(["useGetVersionQuery"], async () => {
    const { data } = await getVersionFn();
    return responseFn(data);
  });

  return queryResult;
};
