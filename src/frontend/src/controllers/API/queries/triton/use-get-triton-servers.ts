import type { useQueryFunctionType } from "@/types/api";
import type { TritonServerType } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type GetTritonServersResponse = TritonServerType[];

export const useGetTritonServers: useQueryFunctionType<
  undefined,
  GetTritonServersResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<GetTritonServersResponse> => {
    const { data } = await api.get<GetTritonServersResponse>(
      `${getURL("TRITON_SERVERS")}/`,
    );
    return data;
  };

  return query(["useGetTritonServers"], responseFn, options ?? {});
};
