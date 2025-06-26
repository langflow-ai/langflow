import { MISSED_ERROR_ALERT } from "@/constants/alerts_constants";
import { BROKEN_EDGES_WARNING } from "@/constants/constants";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import {
  track,
  trackDataLoaded,
  trackFlowBuild,
} from "@/customization/utils/analytics";
import { checkCodeValidity } from "@/CustomNodes/helpers/check-code-validity";
import { brokenEdgeMessage } from "@/utils/utils";
import {
  EdgeChange,
  Node,
  NodeChange,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react";
import { cloneDeep, zip } from "lodash";
import { create } from "zustand";
import { BuildStatus, EventDeliveryType } from "../constants/enums";
import { LogsLogType, VertexBuildTypeAPI } from "../types/api";
import { ChatInputType, ChatOutputType } from "../types/chat";
import {
  AllNodeType,
  EdgeType,
  NodeDataType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import {
  ComponentsToUpdateType,
  FlowStoreType,
  VertexLayerElementType,
} from "../types/zustand/flow";
import { buildFlowVerticesWithFallback } from "../utils/buildUtils";
import {
  buildPositionDictionary,
  checkChatInput,
  cleanEdges,
  detectBrokenEdgesEdges,
  getHandleId,
  getNodeId,
  scapeJSONParse,
  scapedJSONStringfy,
  unselectAllNodesEdges,
  updateGroupRecursion,
  validateEdge,
  validateNodes,
} from "../utils/reactflowUtils";
import { getInputsAndOutputs } from "../utils/storeUtils";
import useAlertStore from "./alertStore";
import { useDarkStore } from "./darkStore";
import useFlowsManagerStore from "./flowsManagerStore";
import { useGlobalVariablesStore } from "./globalVariablesStore/globalVariables";
import { useTweaksStore } from "./tweaksStore";
import { useTypesStore } from "./typesStore";

// this is our useStore hook that we can use in our components to get parts of the store and call actions
const useFlowStore = create<FlowStoreType>((set, get) => ({
  playgroundPage: false,
  setPlaygroundPage: (playgroundPage) => {
    set({ playgroundPage });
  },
  positionDictionary: {},
  setPositionDictionary: (positionDictionary) => {
    set({ positionDictionary });
  },
  isPositionAvailable: (position: { x: number; y: number }) => {
    if (
      get().positionDictionary[position.x] &&
      get().positionDictionary[position.x] === position.y
    ) {
      return false;
    }
    return true;
  },
  fitViewNode: (nodeId) => {
    if (get().reactFlowInstance && get().nodes.find((n) => n.id === nodeId)) {
      get().reactFlowInstance?.fitView({ nodes: [{ id: nodeId }] });
    }
  },
  autoSaveFlow: undefined,
  componentsToUpdate: [],
  setComponentsToUpdate: (change) => {
    let newChange =
      typeof change === "function" ? change(get().componentsToUpdate) : change;
    set({ componentsToUpdate: newChange });
  },
  updateComponentsToUpdate: (nodes) => {
    let outdatedNodes: ComponentsToUpdateType[] = [];
    const templates = useTypesStore.getState().templates;
    nodes.forEach((node) => {
      if (node.type === "genericNode") {
        const codeValidity = checkCodeValidity(node.data, templates);
        if (codeValidity && codeValidity.outdated)
          outdatedNodes.push({
            id: node.id,
            icon: node.data.node?.icon,
            display_name: node.data.node?.display_name,
            outdated: codeValidity.outdated,
            breakingChange: codeValidity.breakingChange,
            userEdited: codeValidity.userEdited,
          });
      }
    });
    set({ componentsToUpdate: outdatedNodes });
  },
  onFlowPage: false,
  setOnFlowPage: (FlowPage) => set({ onFlowPage: FlowPage }),
  flowState: undefined,
  flowBuildStatus: {},
  nodes: [],
  edges: [],
  isBuilding: false,
  stopBuilding: () => {
    get().buildController.abort();
    get().updateEdgesRunningByNodes(
      get().nodes.map((n) => n.id),
      false,
    );
    set({ isBuilding: false });
    get().revertBuiltStatusFromBuilding();
    useAlertStore.getState().setErrorData({
      title: "Build stopped",
    });
  },
  isPending: true,
  setHasIO: (hasIO) => {
    set({ hasIO });
  },
  reactFlowInstance: null,
  lastCopiedSelection: null,
  flowPool: {},
  setInputs: (inputs) => {
    set({ inputs });
  },
  setOutputs: (outputs) => {
    set({ outputs });
  },
  inputs: [],
  outputs: [],
  hasIO: get()?.inputs?.length > 0 || get()?.outputs?.length > 0,
  setFlowPool: (flowPool) => {
    set({ flowPool });
  },
  updateToolMode: (nodeId: string, toolMode: boolean) => {
    get().setNode(nodeId, (node) => {
      let newNode = cloneDeep(node);
      if (newNode.type === "genericNode") {
        newNode.data.node!.tool_mode = toolMode;
      }
      return newNode;
    });
  },
  updateFreezeStatus: (nodeIds: string[], freeze: boolean) => {
    get().setNodes((oldNodes) => {
      const newNodes = cloneDeep(oldNodes);
      return newNodes.map((node) => {
        if (nodeIds.includes(node.id)) {
          (node.data as NodeDataType).node!.frozen = freeze;
        }
        return node;
      });
    });
  },
  addDataToFlowPool: (data: VertexBuildTypeAPI, nodeId: string) => {
    let newFlowPool = cloneDeep({ ...get().flowPool });
    if (!newFlowPool[nodeId]) newFlowPool[nodeId] = [data];
    else {
      newFlowPool[nodeId].push(data);
    }
    get().setFlowPool(newFlowPool);
  },
  getNodePosition: (nodeId: string) => {
    const node = get().nodes.find((node) => node.id === nodeId);
    return node?.position || { x: 0, y: 0 };
  },
  updateFlowPool: (
    nodeId: string,
    data: VertexBuildTypeAPI | ChatOutputType | ChatInputType,
    buildId?: string,
  ) => {
    let newFlowPool = cloneDeep({ ...get().flowPool });
    if (!newFlowPool[nodeId]) {
      return;
    } else {
      let index = newFlowPool[nodeId].length - 1;
      if (buildId) {
        index = newFlowPool[nodeId].findIndex((flow) => flow.id === buildId);
      }
      //check if the data is a flowpool object
      if ((data as VertexBuildTypeAPI).valid !== undefined) {
        newFlowPool[nodeId][index] = data as VertexBuildTypeAPI;
      }
      //update data results
      else {
        newFlowPool[nodeId][index].data.message = data as
          | ChatOutputType
          | ChatInputType;
      }
    }
    get().setFlowPool(newFlowPool);
  },
  CleanFlowPool: () => {
    get().setFlowPool({});
  },
  setPending: (isPending) => {
    set({ isPending });
  },
  resetFlow: (flow) => {
    const nodes = flow?.data?.nodes ?? [];
    const edges = flow?.data?.edges ?? [];
    let brokenEdges = detectBrokenEdgesEdges(nodes, edges);
    if (brokenEdges.length > 0) {
      useAlertStore.getState().setErrorData({
        title: BROKEN_EDGES_WARNING,
        list: brokenEdges.map((edge) => brokenEdgeMessage(edge)),
      });
    }
    let newEdges = cleanEdges(nodes, edges);
    const { inputs, outputs } = getInputsAndOutputs(nodes);
    get().updateComponentsToUpdate(nodes);
    set({
      dismissedNodes: JSON.parse(
        localStorage.getItem(`dismiss_${flow?.id}`) ?? "[]",
      ) as string[],
    });
    unselectAllNodesEdges(nodes, newEdges);
    if (flow?.id) {
      useTweaksStore.getState().initialSetup(nodes, flow?.id);
    }
    set({
      nodes,
      edges: newEdges,
      flowState: undefined,
      buildInfo: null,
      inputs,
      outputs,
      hasIO: inputs.length > 0 || outputs.length > 0,
      flowPool: {},
      currentFlow: flow,
      positionDictionary: {},
    });
  },
  setIsBuilding: (isBuilding) => {
    set({ isBuilding });
  },
  setFlowState: (flowState) => {
    const newFlowState =
      typeof flowState === "function" ? flowState(get().flowState) : flowState;

    if (newFlowState !== get().flowState) {
      set(() => ({
        flowState: newFlowState,
      }));
    }
  },
  setReactFlowInstance: (newState) => {
    set({ reactFlowInstance: newState });
  },
  onNodesChange: (changes: NodeChange<AllNodeType>[]) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },
  onEdgesChange: (changes: EdgeChange<EdgeType>[]) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },
  setNodes: (change) => {
    let newChange = typeof change === "function" ? change(get().nodes) : change;
    let newEdges = cleanEdges(newChange, get().edges);
    const { inputs, outputs } = getInputsAndOutputs(newChange);
    get().updateComponentsToUpdate(newChange);
    set({
      edges: newEdges,
      nodes: newChange,
      flowState: undefined,
      inputs,
      outputs,
      hasIO: inputs.length > 0 || outputs.length > 0,
    });
    get().updateCurrentFlow({ nodes: newChange, edges: newEdges });
    if (get().autoSaveFlow) {
      get().autoSaveFlow!();
    }
  },
  setEdges: (change) => {
    let newChange = typeof change === "function" ? change(get().edges) : change;
    set({
      edges: newChange,
      flowState: undefined,
    });
    get().updateCurrentFlow({ edges: newChange });
    if (get().autoSaveFlow) {
      get().autoSaveFlow!();
    }
  },
  setNode: (
    id: string,
    change: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
    isUserChange: boolean = true,
    callback?: () => void,
  ) => {
    if (!get().nodes.find((node) => node.id === id)) {
      throw new Error("Node not found");
    }

    let newChange =
      typeof change === "function"
        ? change(get().nodes.find((node) => node.id === id)!)
        : change;

    const newNodes = get().nodes.map((node) => {
      if (node.id === id) {
        if (isUserChange) {
          if ((node.data as NodeDataType).node?.frozen) {
            (newChange.data as NodeDataType).node!.frozen = false;
          }
        }
        return newChange;
      }
      return node;
    });

    const newEdges = cleanEdges(newNodes, get().edges);

    set((state) => {
      if (callback) {
        // Defer the callback execution to ensure it runs after state updates are fully applied.
        queueMicrotask(callback);
      }
      return {
        ...state,
        nodes: newNodes,
        edges: newEdges,
      };
    });
    get().updateCurrentFlow({ nodes: newNodes, edges: newEdges });
    if (get().autoSaveFlow) {
      get().autoSaveFlow!();
    }
  },
  getNode: (id: string) => {
    return get().nodes.find((node) => node.id === id);
  },
  deleteNode: (nodeId) => {
    const { filteredNodes, deletedNode } = get().nodes.reduce<{
      filteredNodes: AllNodeType[];
      deletedNode: AllNodeType | null;
    }>(
      (acc, node) => {
        const isMatch =
          typeof nodeId === "string"
            ? node.id === nodeId
            : nodeId.includes(node.id);

        if (isMatch) {
          acc.deletedNode = node;
        } else {
          acc.filteredNodes.push(node);
        }

        return acc;
      },
      { filteredNodes: [], deletedNode: null },
    );

    get().setNodes(filteredNodes);

    if (deletedNode) {
      track("Component Deleted", { componentType: deletedNode.data.type });
    }
  },
  deleteEdge: (edgeId) => {
    get().setEdges(
      get().edges.filter((edge) =>
        typeof edgeId === "string"
          ? edge.id !== edgeId
          : !edgeId.includes(edge.id),
      ),
    );
    track("Component Connection Deleted", { edgeId });
  },
  paste: (selection, position) => {
    // Collect IDs of nodes in the selection
    const selectedNodeIds = new Set(selection.nodes.map((node) => node.id));
    // Find existing edges in the flow that connect nodes within the selection
    const existingEdgesToCopy = get().edges.filter((edge) => {
      return (
        selectedNodeIds.has(edge.source) &&
        selectedNodeIds.has(edge.target) &&
        !selection.edges.some((selEdge) => selEdge.id === edge.id)
      );
    });
    // Add these edges to the selection's edges
    if (existingEdgesToCopy.length > 0) {
      selection.edges = selection.edges.concat(existingEdgesToCopy);
    }

    if (
      selection.nodes.some((node) => node.data.type === "ChatInput") &&
      checkChatInput(get().nodes)
    ) {
      useAlertStore.getState().setNoticeData({
        title: "You can only have one Chat Input component in a flow.",
      });
      selection.nodes = selection.nodes.filter(
        (node) => node.data.type !== "ChatInput",
      );
      selection.edges = selection.edges.filter(
        (edge) =>
          selection.nodes.some((node) => edge.source === node.id) &&
          selection.nodes.some((node) => edge.target === node.id),
      );
    }

    let minimumX = Infinity;
    let minimumY = Infinity;
    let idsMap = {};
    let newNodes: AllNodeType[] = get().nodes;
    let newEdges = get().edges;
    selection.nodes.forEach((node: Node) => {
      if (node.position.y < minimumY) {
        minimumY = node.position.y;
      }
      if (node.position.x < minimumX) {
        minimumX = node.position.x;
      }
    });

    const insidePosition = position.paneX
      ? { x: position.paneX + position.x, y: position.paneY! + position.y }
      : get().reactFlowInstance!.screenToFlowPosition({
          x: position.x,
          y: position.y,
        });

    let internalPostionDictionary = get().positionDictionary;
    if (Object.keys(internalPostionDictionary).length === 0) {
      internalPostionDictionary = buildPositionDictionary(get().nodes);
    }
    while (!get().isPositionAvailable(insidePosition)) {
      insidePosition.x += 10;
      insidePosition.y += 10;
    }
    internalPostionDictionary[insidePosition.x] = insidePosition.y;
    get().setPositionDictionary(internalPostionDictionary);

    selection.nodes.forEach((node: AllNodeType) => {
      // Generate a unique node ID
      let newId = getNodeId(node.data.type);
      idsMap[node.id] = newId;

      // Create a new node object with the correct type
      const newNode = {
        id: newId,
        type: node.type as "genericNode" | "noteNode",
        position: {
          x: insidePosition.x + node.position!.x - minimumX,
          y: insidePosition.y + node.position!.y - minimumY,
        },
        data: {
          ...cloneDeep(node.data),
          id: newId,
        },
      } as AllNodeType;

      updateGroupRecursion(
        newNode,
        selection.edges,
        useGlobalVariablesStore.getState().unavailableFields,
        useGlobalVariablesStore.getState().globalVariablesEntries,
      );

      // Add the new node to the list of nodes in state
      newNodes = newNodes
        .map((node) => ({ ...node, selected: false }))
        .concat({ ...newNode, selected: true });
    });
    get().setNodes(newNodes);

    selection.edges.forEach((edge: EdgeType) => {
      let source = idsMap[edge.source];
      let target = idsMap[edge.target];
      const sourceHandleObject: sourceHandleType = scapeJSONParse(
        edge.sourceHandle!,
      );
      let sourceHandle = scapedJSONStringfy({
        ...sourceHandleObject,
        id: source,
      });
      sourceHandleObject.id = source;

      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!,
      );
      let targetHandle = scapedJSONStringfy({
        ...targetHandleObject,
        id: target,
      });
      targetHandleObject.id = target;

      edge.data = {
        sourceHandle: sourceHandleObject,
        targetHandle: targetHandleObject,
      };

      let id = getHandleId(source, sourceHandle, target, targetHandle);
      newEdges = addEdge(
        {
          source,
          target,
          sourceHandle,
          targetHandle,
          id,
          data: cloneDeep(edge.data),
          selected: false,
        },
        newEdges.map((edge) => ({ ...edge, selected: false })),
      );
    });
    get().setEdges(newEdges);
  },
  setLastCopiedSelection: (newSelection, isCrop = false) => {
    if (isCrop) {
      const nodesIdsSelected = newSelection!.nodes.map((node) => node.id);
      const edgesIdsSelected = newSelection!.edges.map((edge) => edge.id);

      nodesIdsSelected.forEach((id) => {
        get().deleteNode(id);
      });

      edgesIdsSelected.forEach((id) => {
        get().deleteEdge(id);
      });

      const newNodes = get().nodes.filter(
        (node) => !nodesIdsSelected.includes(node.id),
      );
      const newEdges = get().edges.filter(
        (edge) => !edgesIdsSelected.includes(edge.id),
      );

      set({ nodes: newNodes, edges: newEdges });
    }

    set({ lastCopiedSelection: newSelection });
  },
  cleanFlow: () => {
    set({
      nodes: [],
      edges: [],
      flowState: undefined,
      getFilterEdge: [],
    });
  },
  setFilterEdge: (newState) => {
    if (newState.length === 0) {
      set({ filterType: undefined });
    }
    set({ getFilterEdge: newState });
  },
  getFilterEdge: [],
  onConnect: (connection) => {
    const dark = useDarkStore.getState().dark;
    // const commonMarkerProps = {
    //   type: MarkerType.ArrowClosed,
    //   width: 20,
    //   height: 20,
    //   color: dark ? "#555555" : "#000000",
    // };

    // const inputTypes = INPUT_TYPES;
    // const outputTypes = OUTPUT_TYPES;

    // const findNode = useFlowStore
    //   .getState()
    //   .nodes.find(
    //     (node) => node.id === connection.source || node.id === connection.target
    //   );

    // const sourceType = findNode?.data?.type;
    // let isIoIn = false;
    // let isIoOut = false;
    // if (sourceType) {
    //   isIoIn = inputTypes.has(sourceType);
    //   isIoOut = outputTypes.has(sourceType);
    // }

    let newEdges: EdgeType[] = [];
    get().setEdges((oldEdges) => {
      newEdges = addEdge(
        {
          ...connection,
          data: {
            targetHandle: scapeJSONParse(connection.targetHandle!),
            sourceHandle: scapeJSONParse(connection.sourceHandle!),
          },
        },
        oldEdges,
      );

      return newEdges;
    });
  },
  unselectAll: () => {
    let newNodes = cloneDeep(get().nodes);
    newNodes.forEach((node) => {
      node.selected = false;
      let newEdges = cleanEdges(newNodes, get().edges);
      set({
        nodes: newNodes,
        edges: newEdges,
      });
    });
  },
  pastBuildFlowParams: null,
  buildInfo: null,
  setBuildInfo: (buildInfo: { error?: string[]; success?: boolean } | null) => {
    set({ buildInfo });
  },
  buildFlow: async ({
    startNodeId,
    stopNodeId,
    input_value,
    files,
    silent,
    session,
    stream = true,
    eventDelivery = EventDeliveryType.STREAMING,
  }: {
    startNodeId?: string;
    stopNodeId?: string;
    input_value?: string;
    files?: string[];
    silent?: boolean;
    session?: string;
    stream?: boolean;
    eventDelivery?: EventDeliveryType;
  }) => {
    set({
      pastBuildFlowParams: {
        startNodeId,
        stopNodeId,
        input_value,
        files,
        silent,
        session,
        stream,
        eventDelivery,
      },
      buildInfo: null,
    });
    const playgroundPage = get().playgroundPage;
    get().setIsBuilding(true);
    set({ flowBuildStatus: {} });
    const currentFlow = useFlowsManagerStore.getState().currentFlow;
    const setSuccessData = useAlertStore.getState().setSuccessData;
    const setErrorData = useAlertStore.getState().setErrorData;

    const edges = get().edges;
    let error = false;
    let errors: string[] = [];
    for (const edge of edges) {
      const errorsEdge = validateEdge(edge, get().nodes, edges);
      if (errorsEdge.length > 0) {
        error = true;
        errors.push(errorsEdge.join("\n"));
        useAlertStore.getState().addNotificationToHistory({
          title: MISSED_ERROR_ALERT,
          type: "error",
          list: errorsEdge,
        });
      }
    }
    if (error) {
      get().setIsBuilding(false);
      get().setBuildInfo({ error: errors, success: false });
      throw new Error("Invalid components");
    }

    function validateSubgraph(nodes: string[]) {
      const errorsObjs = validateNodes(
        get().nodes.filter((node) => nodes.includes(node.id)),
        get().edges,
      );

      const errors = errorsObjs.map((obj) => obj.errors).flat();
      if (errors.length > 0) {
        get().setBuildInfo({ error: errors, success: false });
        useAlertStore.getState().addNotificationToHistory({
          title: MISSED_ERROR_ALERT,
          type: "error",
          list: errors,
        });
        get().setIsBuilding(false);
        const ids = errorsObjs.map((obj) => obj.id).flat();

        get().updateBuildStatus(ids, BuildStatus.ERROR);
        throw new Error("Invalid components");
      }
      // get().updateEdgesRunningByNodes(nodes, true);
    }
    function handleBuildUpdate(
      vertexBuildData: VertexBuildTypeAPI,
      status: BuildStatus,
      runId: string,
    ) {
      if (vertexBuildData && vertexBuildData.inactivated_vertices) {
        get().removeFromVerticesBuild(vertexBuildData.inactivated_vertices);
        if (vertexBuildData.inactivated_vertices.length > 0) {
          get().updateBuildStatus(
            vertexBuildData.inactivated_vertices,
            BuildStatus.INACTIVE,
          );
        }
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
        let nextVertices: VertexLayerElementType[] = zip(
          next_vertices_ids,
          top_level_vertices,
        ).map(([id, reference]) => ({ id: id!, reference }));

        // Now we filter nextVertices to remove any vertices that are in verticesLayers
        // because they are already being built
        // each layer is a list of vertexlayerelementtypes
        let lastLayer =
          get().verticesBuild!.verticesLayers[
            get().verticesBuild!.verticesLayers.length - 1
          ];

        nextVertices = nextVertices.filter(
          (vertexElement) =>
            !lastLayer.some(
              (layerElement) =>
                layerElement.id === vertexElement.id &&
                layerElement.reference === vertexElement.reference,
            ),
        );
        const newLayers = [
          ...get().verticesBuild!.verticesLayers,
          nextVertices,
        ];
        const newIds = [
          ...get().verticesBuild!.verticesIds,
          ...next_vertices_ids,
        ];
        if (
          ENABLE_DATASTAX_LANGFLOW &&
          vertexBuildData?.id?.includes("AstraDB")
        ) {
          const search_results: LogsLogType[] = Object.values(
            vertexBuildData?.data?.logs?.search_results,
          );
          search_results.forEach((log) => {
            if (
              log.message.includes("Adding") &&
              log.message.includes("documents") &&
              log.message.includes("Vector Store")
            ) {
              trackDataLoaded(
                get().currentFlow?.id,
                get().currentFlow?.name,
                "AstraDB Vector Store",
                vertexBuildData?.id,
              );
            }
          });
        }
        get().updateVerticesBuild({
          verticesIds: newIds,
          verticesLayers: newLayers,
          runId: runId,
          verticesToRun: get().verticesBuild!.verticesToRun,
        });

        get().updateBuildStatus(top_level_vertices, BuildStatus.TO_BUILD);
      }

      get().addDataToFlowPool(
        { ...vertexBuildData, run_id: runId },
        vertexBuildData.id,
      );
      if (status !== BuildStatus.ERROR) {
        get().updateBuildStatus([vertexBuildData.id], status);
      }
    }
    await buildFlowVerticesWithFallback({
      session,
      input_value,
      files,
      flowId: currentFlow!.id,
      startNodeId,
      stopNodeId,
      onGetOrderSuccess: () => {},
      onBuildComplete: (allNodesValid) => {
        const nodeId = startNodeId || stopNodeId;
        if (!silent) {
          if (allNodesValid) {
            get().setBuildInfo({ success: true });
          }
        }
        get().updateEdgesRunningByNodes(
          get().nodes.map((n) => n.id),
          false,
        );
        get().setIsBuilding(false);
        trackFlowBuild(get().currentFlow?.name ?? "Unknown", false, {
          flowId: get().currentFlow?.id,
        });
      },
      onBuildUpdate: handleBuildUpdate,
      onBuildError: (title: string, list: string[], elementList) => {
        const idList =
          (elementList
            ?.map((element) => element.id)
            .filter(Boolean) as string[]) ?? get().nodes.map((n) => n.id);
        useFlowStore.getState().updateBuildStatus(idList, BuildStatus.ERROR);
        if (get().componentsToUpdate.length > 0)
          setErrorData({
            title:
              "There are outdated components in the flow. The error could be related to them.",
          });
        get().updateEdgesRunningByNodes(
          get().nodes.map((n) => n.id),
          false,
        );
        get().setBuildInfo({ error: list, success: false });
        useAlertStore.getState().addNotificationToHistory({
          title: title,
          type: "error",
          list: list,
        });
        get().setIsBuilding(false);
        get().buildController.abort();
        trackFlowBuild(get().currentFlow?.name ?? "Unknown", true, {
          flowId: get().currentFlow?.id,
          error: list,
        });
      },
      onBuildStart: (elementList) => {
        const idList = elementList
          // reference is the id of the vertex or the id of the parent in a group node
          .map((element) => element.reference)
          .filter(Boolean) as string[];
        get().updateBuildStatus(idList, BuildStatus.BUILDING);

        const edges = get().edges;
        const newEdges = edges.map((edge) => {
          if (
            edge.data?.targetHandle &&
            idList.includes(edge.data.targetHandle.id ?? "")
          ) {
            edge.className = "ran";
          }
          return edge;
        });
        set({ edges: newEdges });
      },
      onValidateNodes: validateSubgraph,
      nodes: get().nodes || undefined,
      edges: get().edges || undefined,
      logBuilds: get().onFlowPage,
      playgroundPage,
      eventDelivery,
    });
    get().setIsBuilding(false);
    get().revertBuiltStatusFromBuilding();
  },
  getFlow: () => {
    return {
      nodes: get().nodes,
      edges: get().edges,
      viewport: get().reactFlowInstance?.getViewport()!,
    };
  },
  updateEdgesRunningByNodes: (ids: string[], running: boolean) => {
    const edges = get().edges;
    const newEdges = edges.map((edge) => {
      if (
        edge.data?.sourceHandle &&
        ids.includes(edge.data.sourceHandle.id ?? "")
      ) {
        edge.animated = running;
        edge.className = running ? "running" : "";
      } else {
        edge.animated = false;
        edge.className = "not-running";
      }
      return edge;
    });
    set({ edges: newEdges });
  },
  clearEdgesRunningByNodes: async (): Promise<void> => {
    return new Promise<void>((resolve) => {
      const edges = get().edges;
      const newEdges = edges.map((edge) => {
        edge.animated = false;
        edge.className = "";
        return edge;
      });
      set({ edges: newEdges });
      resolve();
    });
  },

  updateVerticesBuild: (
    vertices: {
      verticesIds: string[];
      verticesLayers: VertexLayerElementType[][];
      runId?: string;
      verticesToRun: string[];
    } | null,
  ) => {
    set({ verticesBuild: vertices });
  },
  verticesBuild: null,
  addToVerticesBuild: (vertices: string[]) => {
    const verticesBuild = get().verticesBuild;
    if (!verticesBuild) return;
    set({
      verticesBuild: {
        ...verticesBuild,
        verticesIds: [...verticesBuild.verticesIds, ...vertices],
      },
    });
  },
  removeFromVerticesBuild: (vertices: string[]) => {
    const verticesBuild = get().verticesBuild;
    if (!verticesBuild) return;
    set({
      verticesBuild: {
        ...verticesBuild,
        // remove the vertices from the list of vertices ids
        // that are going to be built
        verticesIds: get().verticesBuild!.verticesIds.filter(
          // keep the vertices that are not in the list of vertices to remove
          (vertex) => !vertices.includes(vertex),
        ),
      },
    });
  },
  updateBuildStatus: (nodeIdList: string[], status: BuildStatus) => {
    const newFlowBuildStatus = { ...get().flowBuildStatus };
    nodeIdList.forEach((id) => {
      newFlowBuildStatus[id] = {
        status,
      };
      if (status == BuildStatus.BUILT) {
        const timestamp_string = new Date(Date.now()).toLocaleString();
        newFlowBuildStatus[id].timestamp = timestamp_string;
      }
    });
    set({ flowBuildStatus: newFlowBuildStatus });
  },
  revertBuiltStatusFromBuilding: () => {
    const newFlowBuildStatus = { ...get().flowBuildStatus };
    Object.keys(newFlowBuildStatus).forEach((id) => {
      if (newFlowBuildStatus[id].status === BuildStatus.BUILDING) {
        newFlowBuildStatus[id].status = BuildStatus.BUILT;
      }
    });
    set({ flowBuildStatus: newFlowBuildStatus });
  },
  currentFlow: undefined,
  setCurrentFlow: (flow) => {
    set({ currentFlow: flow });
  },
  updateCurrentFlow: ({ nodes, edges }) => {
    set({
      currentFlow: {
        ...get().currentFlow!,
        data: {
          nodes: nodes ?? get().currentFlow?.data?.nodes ?? [],
          edges: edges ?? get().currentFlow?.data?.edges ?? [],
          viewport: get().currentFlow?.data?.viewport ?? {
            x: 0,
            y: 0,
            zoom: 1,
          },
        },
      },
    });
  },
  buildController: new AbortController(),
  setBuildController: (controller) => {
    set({ buildController: controller });
  },
  handleDragging: undefined,
  setHandleDragging: (handleDragging) => {
    set({ handleDragging });
  },

  filterType: undefined,
  setFilterType: (filterType) => {
    set({ filterType });
  },
  currentBuildingNodeId: undefined,
  setCurrentBuildingNodeId: (nodeIds) => {
    set({ currentBuildingNodeId: nodeIds });
  },
  resetFlowState: () => {
    set({
      nodes: [],
      edges: [],
      flowState: undefined,
      hasIO: false,
      inputs: [],
      outputs: [],
      flowPool: {},
      currentFlow: undefined,
      reactFlowInstance: null,
      lastCopiedSelection: null,
      verticesBuild: null,
      flowBuildStatus: {},
      buildInfo: null,
      isBuilding: false,
      isPending: true,
      positionDictionary: {},
      componentsToUpdate: [],
    });
  },
  dismissedNodes: [],
  addDismissedNodes: (dismissedNodes: string[]) => {
    const newDismissedNodes = Array.from(
      new Set([...get().dismissedNodes, ...dismissedNodes]),
    );
    localStorage.setItem(
      `dismiss_${get().currentFlow?.id}`,
      JSON.stringify(newDismissedNodes),
    );
    set({ dismissedNodes: newDismissedNodes });
  },
  removeDismissedNodes: (dismissedNodes: string[]) => {
    const newDismissedNodes = get().dismissedNodes.filter(
      (node) => !dismissedNodes.includes(node),
    );
    localStorage.setItem(
      `dismiss_${get().currentFlow?.id}`,
      JSON.stringify(newDismissedNodes),
    );
    set({ dismissedNodes: newDismissedNodes });
  },
  setNewChatOnPlayground: (newChat: boolean) => {
    set({ newChatOnPlayground: newChat });
  },
  newChatOnPlayground: false,
}));

export default useFlowStore;
