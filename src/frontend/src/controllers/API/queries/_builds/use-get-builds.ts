import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowPoolType } from "@/types/zustand/flow";
import { cleanEdges } from "@/utils/reactflowUtils";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { keepPreviousData } from "@tanstack/react-query";
import { AxiosResponse } from "axios";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface BuildsQueryParams {
  flowId?: string;
  nodeId?: string;
  nodes?: any;
  edges?: any;
  viewport?: any;
}

export interface BuildsQueryResponse {
  files: string[];
}

export const useGetBuildsQuery: useQueryFunctionType<
  BuildsQueryParams,
  AxiosResponse<{ vertex_builds: FlowPoolType }>
> = ({ nodes, edges, viewport, flowId, nodeId }) => {
  const { query } = UseRequestProcessor();

  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const setFlowState = useFlowStore((state) => state.setFlowState);
  const setInputs = useFlowStore((state) => state.setInputs);
  const setOutputs = useFlowStore((state) => state.setOutputs);
  const setHasIO = useFlowStore((state) => state.setHasIO);
  const setFlowPool = useFlowStore((state) => state.setFlowPool);
  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);

  const getBuildsFn = async (
    params: BuildsQueryParams,
  ): Promise<AxiosResponse<{ vertex_builds: FlowPoolType }>> => {
    const config = {};
    config["params"] = { flow_id: params.flowId };

    if (params.nodeId) {
      config["params"] = { nodeId: params.nodeId };
    }

    return await api.get<any>(`${getURL("BUILDS")}`, config);
  };

  const responseFn = async () => {
    let newEdges = cleanEdges(nodes, edges);
    const { inputs, outputs } = getInputsAndOutputs(nodes);

    setNodes(nodes);
    setEdges(newEdges);
    setFlowState(undefined);
    setInputs(inputs);
    setOutputs(outputs);
    setHasIO(inputs.length > 0 || outputs.length > 0);
    reactFlowInstance!.setViewport(viewport);

    const response = await getBuildsFn({
      flowId: currentFlow!.id,
    });

    if (currentFlow) {
      const flowPool = response.data.vertex_builds;
      setFlowPool(flowPool);
    }

    return response;
  };

  const queryResult = query(
    [
      "useGetBuildsQuery",
      {
        flowId,
        nodeId,
      },
    ],
    responseFn,
    {
      placeholderData: keepPreviousData,
    },
  );

  return queryResult;
};
