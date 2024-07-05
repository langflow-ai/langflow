import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { AxiosRequestConfig } from "axios";
import { Edge } from "reactflow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostBuildVertices {
  flowId: string;
  startNodeId?: string | null;
  stopNodeId?: string | null;
  nodes?: Node[];
  Edges?: Edge[];
}

export const usePostBuildVertices: useMutationFunctionType<
  IPostBuildVertices
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postBuildVerticesFn = async (
    payload: IPostBuildVertices,
  ): Promise<any> => {
    const config: AxiosRequestConfig<any> = {};
    if (payload.stopNodeId) {
      config["params"] = { stop_component_id: payload.stopNodeId };
    } else if (payload.startNodeId) {
      config["params"] = { start_component_id: payload.startNodeId };
    }
    const data = {
      data: {},
    };
    if (payload.nodes && payload.Edges) {
      data["data"]["nodes"] = payload.nodes;
      data["data"]["edges"] = payload.Edges;
    }

    const response = await api.post<any>(
      `${getURL("BUILD")}/${payload.flowId}/vertices`,
      data,
      config,
    );

    debugger;

    return response.data;
  };

  const mutation: UseMutationResult<
    IPostBuildVertices,
    any,
    IPostBuildVertices
  > = mutate(
    ["usePostBuildVertices"],
    async (payload: IPostBuildVertices) => {
      const res = await postBuildVerticesFn(payload);
      return res;
    },
    options,
  );

  return mutation;
};
