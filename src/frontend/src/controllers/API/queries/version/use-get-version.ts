import { useQueryFunctionType } from "@/types/api";
import { UseRequestProcessor } from "../../services/request-processor";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { useDarkStore } from "@/stores/darkStore";

interface versionQueryResponse {
    version: string;
    package: string;
};

export const useGetVersionQuery: useQueryFunctionType<undefined, versionQueryResponse> = (_, onFetch) => {
  const { query } = UseRequestProcessor();

  const responseFn = (data: any) => {
    if (!onFetch) return data;
    if (typeof onFetch === "function") return onFetch(data);
    const refreshVersion = useDarkStore.getState().refreshVersion;
    switch (onFetch) {
      case "GetVersion": {
        return refreshVersion(data.version);
      }
      default:
        return refreshVersion(data.version);
    }
  };

  const getVersionFn = async () => {
    return await api.get<versionQueryResponse>(
      `${getURL("VERSION")}`
    )
  }

  const queryResult = query(
    ['useGetVersionQuery'],
    async () => {
      const { data } = await getVersionFn();
      responseFn(data);
      return {};
    }
  );

  return queryResult;
}
