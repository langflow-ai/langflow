import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import { cloneDeep, zip } from "lodash";
import { create } from "zustand";
import { checkCodeValidity } from "@/CustomNodes/helpers/check-code-validity";
import { queryClient } from "@/contexts";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_INSPECTION_PANEL,
} from "@/customization/feature-flags";
import {
  track,
  trackDataLoaded,
  trackFlowBuild,
} from "@/customization/utils/analytics";
import { brokenEdgeMessage } from "@/utils/utils";
import { BuildStatus, EventDeliveryType } from "../constants/enums";
import i18n from "../i18n";
import type { LogsLogType, VertexBuildTypeAPI } from "../types/api";
import type { ChatInputType, ChatOutputType } from "../types/chat";
import type {
  AllNodeType,
  EdgeType,
  NodeDataType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import type {
  ComponentsToUpdateType,
  FlowStoreType,
  VertexLayerElementType,
} from "../types/zustand/flow";
import { buildFlowVerticesWithFallback } from "../utils/buildUtils";
import { filterPlaceableSelection } from "../utils/componentConstraints";
import {
  buildPositionDictionary,
  cleanEdges,
  getConnectedSubgraph,
  getHandleId,
  getNodeId,
  scapedJSONStringfy,
  scapeJSONParse,
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
import { useUtilityStore } from "./utilityStore";

// Tracks in-progress node update operations (e.g. validateComponentCode calls).
// buildFlow awaits these so "Run" doesn't race against a pending "Update".
const pendingNodeUpdates = new Map<
  string,
  { promise: Promise<void>; resolve: () => void }
>();

export function registerNodeUpdate(nodeId: string): void {
  // If there's already a pending update for this node, leave it
  if (pendingNodeUpdates.has(nodeId)) return;
  let resolveRef: () => void;
  const promise = new Promise<void>((r) => {
    resolveRef = r;
  });
  pendingNodeUpdates.set(nodeId, { promise, resolve: resolveRef! });
}

export function completeNodeUpdate(nodeId: string): void {
  const entry = pendingNodeUpdates.get(nodeId);
  if (entry) {
    entry.resolve();
    pendingNodeUpdates.delete(nodeId);
  }
}

export async function waitForNodeUpdates(
  timeoutMs: number = 10_000,
): Promise<void> {
  if (pendingNodeUpdates.size === 0) return;
  const pendingIds = Array.from(pendingNodeUpdates.keys());
  const promises = Array.from(pendingNodeUpdates.values()).map(
    (e) => e.promise,
  );
  let timedOut = false;
  await Promise.race([
    Promise.all(promises),
    new Promise<void>((resolve) =>
      setTimeout(() => {
        timedOut = true;
        resolve();
      }, timeoutMs),
    ),
  ]);
  if (timedOut) {
    console.warn(
      `waitForNodeUpdates timed out after ${timeoutMs}ms. ` +
        `${pendingNodeUpdates.size} updates still pending: ${pendingIds.join(", ")}`,
    );
  }
}

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
    const newChange =
      typeof change === "function" ? change(get().componentsToUpdate) : change;
    set({ componentsToUpdate: newChange });
  },
  updateComponentsToUpdate: (nodes) => {
    const outdatedNodes: ComponentsToUpdateType[] = [];
    const templates = useTypesStore.getState().templates;
    const allowCustomComponents =
      useUtilityStore.getState().allowCustomComponents;
    nodes.forEach((node) => {
      if (node.type === "genericNode") {
        const codeValidity = checkCodeValidity(
          node.data,
          templates,
          allowCustomComponents,
        );
        if (codeValidity && (codeValidity.outdated || codeValidity.blocked))
          outdatedNodes.push({
            id: node.id,
            icon: node.data.node?.icon,
            display_name: node.data.node?.display_name,
            outdated: codeValidity.outdated,
            blocked: codeValidity.blocked,
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
  buildStartTime: null,
  buildDuration: null,
  buildingFlowId: null,
  buildingSessionId: null,
  stopBuilding: () => {
    get().buildController.abort();
    get().updateEdgesRunningByNodes(
      get().nodes.map((n) => n.id),
      false,
    );
    set({ isBuilding: false });
    get().revertBuiltStatusFromBuilding();
    useAlertStore.getState().setErrorData({
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      title: (i18n as any).t("alerts.buildStopped"),
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
      const newNode = cloneDeep(node);
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
    const prevPool = get().flowPool;
    const prevEntries = prevPool[nodeId];
    const newFlowPool = {
      ...prevPool,
      [nodeId]: prevEntries ? [...prevEntries, data] : [data],
    };
    get().setFlowPool(newFlowPool);
  },
  appendLogToFlowPool: (
    nodeId: string,
    outputName: string,
    log: LogsLogType,
  ) => {
    const prevPool = get().flowPool;
    const prevEntries = prevPool[nodeId];
    if (!prevEntries || prevEntries.length === 0) {
      const newEntry: VertexBuildTypeAPI = {
        id: nodeId,
        inactivated_vertices: null,
        next_vertices_ids: [],
        top_level_vertices: [],
        valid: true,
        data: {
          results: {},
          outputs: {},
          logs: { [outputName]: [log] },
          messages: [],
        },
        timestamp: new Date().toISOString(),
        params: null,
        messages: [],
        artifacts: null,
      };
      get().setFlowPool({ ...prevPool, [nodeId]: [newEntry] });
    } else {
      const latest = prevEntries[prevEntries.length - 1];
      const existingLogs: LogsLogType[] = latest.data.logs[outputName] ?? [];
      const updatedEntry: VertexBuildTypeAPI = {
        ...latest,
        data: {
          ...latest.data,
          logs: {
            ...latest.data.logs,
            [outputName]: [...existingLogs, log],
          },
        },
      };
      get().setFlowPool({
        ...prevPool,
        [nodeId]: [...prevEntries.slice(0, -1), updatedEntry],
      });
    }
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
    const newFlowPool = cloneDeep({ ...get().flowPool });
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
    const { edges: newEdges, brokenEdges } = cleanEdges(nodes, edges);

    if (brokenEdges.length > 0) {
      useAlertStore.getState().setErrorData({
        title: i18n.t("flow.brokenEdgesWarning"),
        list: brokenEdges.map((edge) => brokenEdgeMessage(edge)),
      });
    }
    const { inputs, outputs } = getInputsAndOutputs(nodes);
    get().updateComponentsToUpdate(nodes);
    set({
      dismissedNodes: JSON.parse(
        localStorage.getItem(`dismiss_${flow?.id}`) ?? "[]",
      ) as string[],
      dismissedNodesLegacy: JSON.parse(
        localStorage.getItem(`dismiss_legacy_${flow?.id}`) ?? "[]",
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
      rightClickedNodeId: null,
    });
    // Patch translatable fields if types are already loaded in the new language
    syncNodeTranslations();
  },
  setIsBuilding: (isBuilding) => {
    const current = get();
    set({
      isBuilding,
      // Reset buildStartTime and buildDuration when a new build begins
      buildStartTime:
        isBuilding && !current.isBuilding ? null : current.buildStartTime,
      buildDuration:
        isBuilding && !current.isBuilding ? null : current.buildDuration,
      // Clear building session when build ends
      buildingFlowId: !isBuilding ? null : current.buildingFlowId,
      buildingSessionId: !isBuilding ? null : current.buildingSessionId,
    });
  },
  setBuildStartTime: (time) => {
    set({ buildStartTime: time });
  },
  setBuildDuration: (duration) => {
    set({ buildDuration: duration });
  },
  setBuildingSession: (flowId, sessionId) => {
    set({ buildingFlowId: flowId, buildingSessionId: sessionId });
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
    const newChange =
      typeof change === "function" ? change(get().nodes) : change;
    const { edges: newEdges } = cleanEdges(newChange, get().edges);
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
    const newChange =
      typeof change === "function" ? change(get().edges) : change;
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

    const newChange =
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

    const { edges: newEdges } = cleanEdges(newNodes, get().edges);

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

    // Clear rightClickedNodeId if the deleted node was right-clicked
    const rightClickedNodeId = get().rightClickedNodeId;
    if (rightClickedNodeId && deletedNode) {
      const isRightClickedNodeDeleted =
        typeof nodeId === "string"
          ? nodeId === rightClickedNodeId
          : nodeId.includes(rightClickedNodeId);

      if (isRightClickedNodeDeleted) {
        set({ rightClickedNodeId: null });
      }
    }

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
    if (get().currentFlow?.locked) return;
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

    // Enforce component placement constraints (singleton + mutual exclusivity)
    // on paste so they cannot be bypassed by copy/paste, matching the sidebar.
    // The filter is side-effect free; surfacing the notice is the caller's job.
    const placeable = filterPlaceableSelection(selection, get().nodes);
    selection.nodes = placeable.nodes;
    selection.edges = placeable.edges;
    if (placeable.violations.length > 0) {
      const messages: string[] = [];
      if (placeable.violations.some((v) => v.reason === "singleton")) {
        messages.push(i18n.t("flow.duplicateComponentsNotPasted"));
      }
      if (placeable.violations.some((v) => v.reason === "exclusivity")) {
        messages.push(i18n.t("flow.exclusiveComponentsNotPasted"));
      }
      useAlertStore.getState().setNoticeData({ title: messages.join(" ") });
    }

    let minimumX = Infinity;
    let minimumY = Infinity;
    const idsMap = {};
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
      const newId = getNodeId(node.data.type);
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
        // Preserve width and height for noteNodes (sticky notes)
        ...(node.width !== undefined && { width: node.width }),
        ...(node.height !== undefined && { height: node.height }),
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
      const source = idsMap[edge.source];
      const target = idsMap[edge.target];
      const sourceHandleObject: sourceHandleType = scapeJSONParse(
        edge.sourceHandle!,
      );
      const sourceHandle = scapedJSONStringfy({
        ...sourceHandleObject,
        id: source,
      });
      sourceHandleObject.id = source;

      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!,
      );
      const targetHandle = scapedJSONStringfy({
        ...targetHandleObject,
        id: target,
      });
      targetHandleObject.id = target;

      edge.data = {
        sourceHandle: sourceHandleObject,
        targetHandle: targetHandleObject,
      };

      const id = getHandleId(source, sourceHandle, target, targetHandle);
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
  setFilterComponent: (newState) => {
    set({ getFilterComponent: newState });
  },
  getFilterComponent: "",
  rightClickedNodeId: null,
  setRightClickedNodeId: (nodeId) => {
    set({ rightClickedNodeId: nodeId });
  },
  onConnect: (connection) => {
    const _dark = useDarkStore.getState().dark;
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
    const newNodes = cloneDeep(get().nodes);
    newNodes.forEach((node) => {
      node.selected = false;
    });
    const { edges: newEdges } = cleanEdges(newNodes, get().edges);
    set({
      nodes: newNodes,
      edges: newEdges,
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
    const setErrorData = useAlertStore.getState().setErrorData;

    const edges = get().edges;
    let errors: string[] = [];

    // Only validate upstream nodes/edges if startNodeId is provided
    let nodesToValidate = get().nodes;
    let edgesToValidate = edges;
    if (startNodeId) {
      const downstream = getConnectedSubgraph(
        startNodeId,
        get().nodes,
        edges,
        "downstream",
      );
      nodesToValidate = downstream.nodes;
      edgesToValidate = downstream.edges;
    } else if (stopNodeId) {
      get().setStopNodeId(stopNodeId);
      const upstream = getConnectedSubgraph(
        stopNodeId,
        get().nodes,
        edges,
        "upstream",
      );
      nodesToValidate = upstream.nodes;
      edgesToValidate = upstream.edges;
    }
    if (!stopNodeId) {
      get().setStopNodeId(undefined);
    }

    for (const edge of edgesToValidate) {
      const errorsEdge = validateEdge(edge, nodesToValidate, edgesToValidate);
      if (errorsEdge.length > 0) {
        errors.push(errorsEdge.join("\n"));
      }
    }
    const errorsObjs = validateNodes(nodesToValidate, edges);

    errors = errors.concat(errorsObjs.flatMap((obj) => obj.errors));
    if (errors.length > 0) {
      setErrorData({
        title: i18n.t("errors.missedFields"),
        list: errors,
      });
      const ids = errorsObjs.flatMap((obj) => obj.id);
      get().updateBuildStatus(ids, BuildStatus.ERROR); // Set only the build status as error without adding info to the flow pool

      get().setIsBuilding(false);
      throw new Error("Invalid components");
    }

    // Wait for any in-progress component updates (e.g. user clicked "Update"
    // then immediately clicked "Run") before checking outdated state.
    await waitForNodeUpdates();

    // Block build when custom components are disabled and there are outdated components
    // Recalculate from current nodes to avoid stale componentsToUpdate
    // (setNode does not trigger updateComponentsToUpdate, only setNodes does)
    get().updateComponentsToUpdate(get().nodes);
    const allowCustomComponents =
      useUtilityStore.getState().allowCustomComponents;
    if (!allowCustomComponents && get().componentsToUpdate.length > 0) {
      const blockedComponents = get().componentsToUpdate.filter(
        (component) => component.blocked,
      );
      const outdatedComponents = get().componentsToUpdate.filter(
        (component) => component.outdated,
      );
      const errorList: string[] = [];

      if (blockedComponents.length > 0) {
        errorList.push(
          `The following custom components cannot run while custom components are disabled: ${blockedComponents
            .map((component) => component.display_name ?? component.id)
            .join(", ")}`,
        );
      }

      if (outdatedComponents.length > 0) {
        errorList.push(
          `The following components are outdated and must be updated: ${outdatedComponents
            .map((component) => component.display_name ?? component.id)
            .join(", ")}`,
        );
      }

      setErrorData({
        title:
          blockedComponents.length > 0
            ? "Custom components are blocked while custom components are disabled"
            : "Outdated components must be updated before building",
        list: errorList,
      });
      get().setIsBuilding(false);
      throw new Error(
        blockedComponents.length > 0
          ? "Custom components are blocked while custom components are disabled"
          : "Outdated components must be updated",
      );
    }

    function validateSubgraph() {}
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
        const lastLayer =
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
        // Invalidate KB-related caches so any KnowledgeIngestion node
        // that ran inside this build surfaces its updated stats / runs
        // the next time the user opens the assets/knowledge-bases tab.
        // Cheap when no subscribers are mounted; the queries only
        // refetch if a component is actively reading them.
        queryClient.invalidateQueries({ queryKey: ["useGetKnowledgeBases"] });
        queryClient.invalidateQueries({ queryKey: ["useGetIngestionRuns"] });
        queryClient.invalidateQueries({
          queryKey: ["useGetKnowledgeBaseChunks"],
        });
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
        const isCustomComponentBlocked = list.some((msg) =>
          msg.toLowerCase().includes("custom components are not allowed"),
        );
        if (!isCustomComponentBlocked && get().componentsToUpdate.length > 0)
          setErrorData({
            title: i18n.t("errors.blockedComponents"),
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
        ids.includes(edge.data.sourceHandle.id ?? "") &&
        edge.data.sourceHandle.id !== get().stopNodeId
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
  clearAndSetEdgesRunning: (nextIds?: string[]) => {
    const edges = get().edges;
    const stopNodeId = get().stopNodeId;
    const nextIdSet = nextIds ? new Set(nextIds) : null;

    const newEdges = edges.map((edge) => {
      const sourceId = edge.data?.sourceHandle?.id ?? "";
      if (nextIdSet && nextIdSet.has(sourceId) && sourceId !== stopNodeId) {
        return { ...edge, animated: true, className: "running" };
      }
      return { ...edge, animated: false, className: "" };
    });
    set({ edges: newEdges });
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
      rightClickedNodeId: null,
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
  dismissedNodesLegacy: [],
  addDismissedNodesLegacy: (dismissedNodes: string[]) => {
    const newDismissedNodes = Array.from(
      new Set([...get().dismissedNodesLegacy, ...dismissedNodes]),
    );
    localStorage.setItem(
      `dismiss_legacy_${get().currentFlow?.id}`,
      JSON.stringify(newDismissedNodes),
    );
    set({ dismissedNodesLegacy: newDismissedNodes });
  },
  helperLineEnabled: false,
  setHelperLineEnabled: (helperLineEnabled: boolean) => {
    set({ helperLineEnabled });
  },
  inspectionPanelVisible: ENABLE_INSPECTION_PANEL
    ? localStorage.getItem("inspectionPanelVisible") !== null
      ? localStorage.getItem("inspectionPanelVisible") === "true"
      : true
    : false,
  setInspectionPanelVisible: (visible: boolean) => {
    if (!ENABLE_INSPECTION_PANEL) return;
    localStorage.setItem("inspectionPanelVisible", String(visible));
    set({ inspectionPanelVisible: visible });
  },
  setNewChatOnPlayground: (newChat: boolean) => {
    set({ newChatOnPlayground: newChat });
  },
  newChatOnPlayground: false,
  stopNodeId: undefined,
  setStopNodeId: (nodeId: string | undefined) => {
    set({ stopNodeId: nodeId });
  },
}));

export function recomputeComponentsToUpdateIfNeeded(): void {
  const { nodes, updateComponentsToUpdate } = useFlowStore.getState();
  if (nodes.length > 0) {
    updateComponentsToUpdate(nodes);
  }
}

/** Normalize a component key: strip spaces, lowercase. Mirrors backend normalize_component_key(). */
function normalizeComponentKey(name: string): string {
  return name.replace(/\s+/g, "").toLowerCase();
}

export function syncNodeTranslations(): void {
  const { nodes } = useFlowStore.getState();
  if (nodes.length === 0) return;

  const {
    data: typesData,
    types,
    templates,
    componentDisplayNames,
  } = useTypesStore.getState();

  // Build normalized lookup: normalize(registryKey) → registryKey
  // This lets us find "Prompt Template" in the registry when nodeType is "PromptTemplate".
  const normalizedToRegistryKey: Record<string, string> = {};
  for (const category of Object.values(typesData)) {
    for (const registryKey of Object.keys(
      category as Record<string, unknown>,
    )) {
      normalizedToRegistryKey[normalizeComponentKey(registryKey)] = registryKey;
    }
  }

  let _noteIndex = 0;
  const updatedNodes = nodes.map((node) => {
    const nodeType = node.data.type;

    // Skip note nodes — translations are handled by useGetNoteTranslationsQuery
    if (node.type === "noteNode") {
      _noteIndex += 1;
      return node;
    }

    // Resolve category: try exact match first, then normalized match
    const category =
      types[nodeType] ??
      types[normalizedToRegistryKey[normalizeComponentKey(nodeType)] ?? ""];

    // Resolve registry key: exact match first, then normalized match
    const registryKey =
      typesData[category]?.[nodeType] !== undefined
        ? nodeType
        : (normalizedToRegistryKey[normalizeComponentKey(nodeType)] ??
          nodeType);

    // Resolve definition: normal path first, then fall back to templates which
    // has legacy aliases pre-resolved (e.g. "Prompt" → Prompt Template definition,
    // "parser" → ParserComponent definition).
    const freshDef =
      category && typesData[category]?.[registryKey]
        ? typesData[category][registryKey]
        : templates[nodeType];

    if (!freshDef) return node;

    // Determine whether display_name / description are default (safe to translate)
    // or user-customized (leave alone). A value is "default" if it appears in the
    // known-translations set for this component type across any supported locale.
    const normKey = normalizeComponentKey(nodeType);
    const knownNames = componentDisplayNames[normKey]?.display_name ?? [];
    const knownDescs = componentDisplayNames[normKey]?.description ?? [];
    const shouldTranslateName = knownNames.includes(
      node.data.node!.display_name,
    );
    const shouldTranslateDesc = knownDescs.includes(
      node.data.node!.description,
    );

    // Update input field display_names, info (tooltips), and placeholders.
    // Before overwriting a field's display_name, verify that the currently
    // saved value is a known translatable string for that field (i.e. it
    // matches one of the locale translations we collected at startup).
    // If the saved value is not in the known set it was user-customized in
    // the component code and must not be overwritten.
    const updatedTemplate = { ...node.data.node!.template };
    const knownFields = componentDisplayNames[normKey]?.fields ?? {};
    for (const fieldName of Object.keys(updatedTemplate)) {
      const freshField = freshDef.template?.[fieldName];
      if (freshField?.display_name !== undefined) {
        const currentDisplayName = updatedTemplate[fieldName]?.display_name;
        const knownFieldDisplayNames =
          knownFields[fieldName]?.display_name ?? [];
        const isKnownTranslation =
          knownFieldDisplayNames.length === 0 ||
          knownFieldDisplayNames.includes(currentDisplayName);
        if (isKnownTranslation) {
          updatedTemplate[fieldName] = {
            ...updatedTemplate[fieldName],
            display_name: freshField.display_name,
            ...(freshField.info !== undefined && { info: freshField.info }),
            ...(freshField.placeholder !== undefined && {
              placeholder: freshField.placeholder,
            }),
          };
        }
      }
    }

    // Update output display_names and info
    const updatedOutputs = node.data.node!.outputs?.map((output, i) => {
      const freshOut = freshDef.outputs?.[i];
      return freshOut
        ? {
            ...output,
            ...(freshOut.display_name !== undefined && {
              display_name: freshOut.display_name,
            }),
            ...(freshOut.info !== undefined && { info: freshOut.info }),
          }
        : output;
    });

    return {
      ...node,
      data: {
        ...node.data,
        node: {
          ...node.data.node!,
          ...(shouldTranslateName && { display_name: freshDef.display_name }),
          ...(shouldTranslateDesc && { description: freshDef.description }),
          template: updatedTemplate,
          ...(updatedOutputs && { outputs: updatedOutputs }),
        },
      },
    };
  });

  useFlowStore.setState({ nodes: updatedNodes });
}

/**
 * Apply translated note node descriptions to the canvas.
 * Called from NoteNode when note_translations endpoint data arrives.
 * translations is a map of node_id → translated markdown text.
 */
export function syncNoteTranslations(
  translations: Record<string, string>,
): void {
  const { nodes } = useFlowStore.getState();
  const updatedNodes = nodes.map((node) => {
    if (node.type !== "noteNode") return node;
    const translated = translations[node.id];
    if (!translated) return node;
    return {
      ...node,
      data: {
        ...node.data,
        node: { ...node.data.node!, description: translated },
      },
    };
  });
  useFlowStore.setState({ nodes: updatedNodes });
}

export default useFlowStore;
