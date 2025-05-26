import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchInstallMCPParams {
  project_id: string;
}

interface PatchInstallMCPResponse {
  message: string;
}

interface PatchInstallMCPBody {
  client: string;
}

export const usePatchInstallMCP: useMutationFunctionType<
  PatchInstallMCPParams,
  PatchInstallMCPBody,
  PatchInstallMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchInstallMCP(body: PatchInstallMCPBody): Promise<any> {
    const res = await api.post(
      `${getURL("MCP")}/${params.project_id}/install`,
      body,
    );
    return res.data.message;
  }

  const mutation: UseMutationResult<
    PatchInstallMCPResponse,
    any,
    PatchInstallMCPBody
  > = mutate(["usePatchInstallMCP"], patchInstallMCP, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetInstalledMCP", params.project_id],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
