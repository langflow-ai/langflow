import {
  FLOW_BUILD_SUCCESS_ALERT,
  MISSED_ERROR_ALERT,
} from "@/constants/alerts_constants";
import { BuildStatus } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { VertexBuildTypeAPI, useMutationFunctionType } from "@/types/api";
import { VertexLayerElementType } from "@/types/zustand/flow";
import { buildVertices } from "@/utils/buildUtils";
import { validateNodes } from "@/utils/reactflowUtils";
import { UseMutationResult } from "@tanstack/react-query";
import { AxiosRequestConfig } from "axios";
import { zip } from "lodash";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostBuildVertices {
  input_value?;
  files?;
  silent?;
  setLockChat?;
  startNodeId?;
  stopNodeId?;
}

export const usePostBuildVertices: useMutationFunctionType<
  IPostBuildVertices
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postBuildVerticesFn = async (
    payload: IPostBuildVertices,
  ): Promise<any> => {
    const setIsBuilding = useFlowStore.getState().setIsBuilding;
    const verticesBuild = useFlowStore.getState().verticesBuild;
    const updateVerticesBuild = useFlowStore.getState().updateVerticesBuild;
    const addDataToFlowPool = useFlowStore.getState().addDataToFlowPool;
    const removeFromVerticesBuild =
      useFlowStore.getState().removeFromVerticesBuild;
    const updateBuildStatus = useFlowStore.getState().updateBuildStatus;
    const revertBuiltStatusFromBuilding =
      useFlowStore.getState().revertBuiltStatusFromBuilding;
    const flowBuildStatus = useFlowStore.getState().flowBuildStatus;
    const nodesStore = useFlowStore.getState().nodes;
    const edges = useFlowStore.getState().edges;
    const onFlowPage = useFlowStore.getState().onFlowPage;

    setIsBuilding(true);
    const currentFlow = useFlowsManagerStore.getState().currentFlow;
    const setSuccessData = useAlertStore.getState().setSuccessData;
    const setErrorData = useAlertStore.getState().setErrorData;
    const setNoticeData = useAlertStore.getState().setNoticeData;

    let response;

    function validateSubgraph(nodes: string[]) {
      const errorsObjs = validateNodes(
        nodesStore.filter((node) => nodes.includes(node.id)),
        edges,
      );

      const errors = errorsObjs.map((obj) => obj.errors).flat();
      if (errors.length > 0) {
        setErrorData({
          title: MISSED_ERROR_ALERT,
          list: errors,
        });
        setIsBuilding(false);
        const ids = errorsObjs.map((obj) => obj.id).flat();

        updateBuildStatus(ids, BuildStatus.ERROR);
        throw new Error("Invalid components");
      }
    }

    function handleBuildUpdate(
      vertexBuildData: VertexBuildTypeAPI,
      status: BuildStatus,
      runId: string,
    ) {
      if (vertexBuildData && vertexBuildData.inactivated_vertices) {
        removeFromVerticesBuild(vertexBuildData.inactivated_vertices);
        updateBuildStatus(
          vertexBuildData.inactivated_vertices,
          BuildStatus.INACTIVE,
        );
      }

      if (vertexBuildData.next_vertices_ids) {
        // next_vertices_ids is a list of vertices that are going to be built next
        // verticesLayers is a list of list of vertices ids, where each list is a layer of vertices
        // we want to add a new layer (next_vertices_ids) to the list of layers (verticesLayers)
        // and the values of next_vertices_ids to the list of vertices ids (verticesIds)

        // const nextVertices will be the zip of vertexBuildData.next_vertices_ids and
        // vertexBuildData.top_level_vertices
        // the VertexLayerElementType as {id: next_vertices_id, layer: top_level_vertex}

        // next_vertices_ids should be next_vertices_ids without the inactivated vertices
        const next_vertices_ids = vertexBuildData.next_vertices_ids.filter(
          (id) => !vertexBuildData.inactivated_vertices?.includes(id),
        );
        const top_level_vertices = vertexBuildData.top_level_vertices.filter(
          (vertex) => !vertexBuildData.inactivated_vertices?.includes(vertex),
        );
        const nextVertices: VertexLayerElementType[] = zip(
          next_vertices_ids,
          top_level_vertices,
        ).map(([id, reference]) => ({ id: id!, reference }));

        const newLayers = [...verticesBuild!.verticesLayers, nextVertices];
        const newIds = [...verticesBuild!.verticesIds, ...next_vertices_ids];
        updateVerticesBuild({
          verticesIds: newIds,
          verticesLayers: newLayers,
          runId: runId,
          verticesToRun: verticesBuild!.verticesToRun,
        });

        updateBuildStatus(top_level_vertices, BuildStatus.TO_BUILD);
      }

      addDataToFlowPool(
        { ...vertexBuildData, run_id: runId },
        vertexBuildData.id,
      );

      useFlowStore.getState().updateBuildStatus([vertexBuildData.id], status);

      const verticesIds = verticesBuild?.verticesIds;
      const newFlowBuildStatus = { ...flowBuildStatus };
      // filter out the vertices that are not status

      const verticesToUpdate = verticesIds?.filter(
        (id) => newFlowBuildStatus[id]?.status !== BuildStatus.BUILT,
      );

      if (verticesToUpdate) {
        useFlowStore.getState().updateBuildStatus(verticesToUpdate, status);
      }
    }

    try {
      const config: AxiosRequestConfig<any> = {};

      if (payload.stopNodeId) {
        config["params"] = { stop_component_id: payload.stopNodeId };
      } else if (payload.startNodeId) {
        config["params"] = { start_component_id: payload.startNodeId };
      }
      const data = {
        data: {},
      };
      if (nodesStore && edges) {
        data["data"]["nodes"] = nodesStore;
        data["data"]["edges"] = edges;
      }

      response = await api.post<any>(
        `${getURL("BUILD")}/${currentFlow!.id}/vertices`,
        data,
        config,
      );
    } catch (error: any) {
      setErrorData({
        title: "Oops! Looks like you missed something",
        list: [error.response?.data?.detail ?? "Unknown Error"],
      });
      useFlowStore.getState().setIsBuilding(false);
      payload.setLockChat && payload.setLockChat(false);
      throw new Error("Invalid components");
    }

    await buildVertices({
      input_value: payload.input_value,
      files: payload.files,
      flowId: currentFlow!.id,
      startNodeId: payload.startNodeId,
      stopNodeId: payload.stopNodeId,
      setLockChat: payload.setLockChat,
      onGetOrderSuccess: () => {
        if (!payload.silent) {
          setNoticeData({ title: "Running components" });
        }
      },
      onBuildComplete: (allNodesValid) => {
        const nodeId = payload.startNodeId || payload.stopNodeId;
        if (!payload.silent) {
          if (allNodesValid) {
            setSuccessData({
              title: nodeId
                ? `${
                    nodesStore.find((node) => node.id === nodeId)?.data.node
                      ?.display_name
                  } built successfully`
                : FLOW_BUILD_SUCCESS_ALERT,
            });
          }
        }
        setIsBuilding(false);
      },
      onBuildUpdate: handleBuildUpdate,
      onBuildError: (title: string, list: string[], elementList) => {
        const idList = elementList
          .map((element) => element.id)
          .filter(Boolean) as string[];
        useFlowStore.getState().updateBuildStatus(idList, BuildStatus.BUILT);
        setErrorData({ list, title });
        setIsBuilding(false);
      },
      onBuildStart: (elementList) => {
        const idList = elementList
          // reference is the id of the vertex or the id of the parent in a group node
          .map((element) => element.reference)
          .filter(Boolean) as string[];
        useFlowStore.getState().updateBuildStatus(idList, BuildStatus.BUILDING);
      },
      onValidateNodes: validateSubgraph,
      nodes: !onFlowPage ? nodesStore : undefined,
      edges: !onFlowPage ? edges : undefined,
      orderResponse: response,
    });

    setIsBuilding(false);

    revertBuiltStatusFromBuilding();
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
