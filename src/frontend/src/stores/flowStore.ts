import { cloneDeep } from "lodash";
import {
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "reactflow";
import { create } from "zustand";
import { FLOW_BUILD_SUCCESS_ALERT, MISSED_ERROR_ALERT } from "../constants/alerts_constants";
import { BuildStatus } from "../constants/enums";
import { getFlowPool, updateFlowInDatabase } from "../controllers/API";
import { VertexBuildTypeAPI } from "../types/api";
import {
  NodeDataType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import { FlowPoolObjectType, FlowStoreType } from "../types/zustand/flow";
import { buildVertices } from "../utils/buildUtils";
import {
  cleanEdges,
  getHandleId,
  getNodeId,
  scapeJSONParse,
  scapedJSONStringfy,
  validateNodes,
} from "../utils/reactflowUtils";
import { getInputsAndOutputs } from "../utils/storeUtils";
import useAlertStore from "./alertStore";
import { useDarkStore } from "./darkStore";
import useFlowsManagerStore from "./flowsManagerStore";

// this is our useStore hook that we can use in our components to get parts of the store and call actions
const useFlowStore = create<FlowStoreType>((set, get) => ({
  flowState: undefined,
  flowBuildStatus: {},
  nodes: [],
  edges: [],
  isBuilding: false,
  isPending: true,
  hasIO: false,
  reactFlowInstance: null,
  lastCopiedSelection: null,
  flowPool: {},
  inputs: [],
  outputs: [],
  setFlowPool: (flowPool) => {
    set({ flowPool });
  },
  addDataToFlowPool: (data: any, nodeId: string) => {
    let newFlowPool = cloneDeep({ ...get().flowPool });
    if (!newFlowPool[nodeId]) newFlowPool[nodeId] = [data];
    else {
      newFlowPool[nodeId].push(data);
    }
    get().setFlowPool(newFlowPool);
  },
  updateFlowPool:(nodeId:string,data:FlowPoolObjectType,buildId?:string)=>{
    let newFlowPool = cloneDeep({ ...get().flowPool });
    if (!newFlowPool[nodeId]){
      return;
    }
    else {
      let index = newFlowPool[nodeId].length-1;
      if(buildId){
        index = newFlowPool[nodeId].findIndex((flow)=>flow.id===buildId);
      }
      newFlowPool[nodeId][index] = data;
    }
    get().setFlowPool(newFlowPool);
  },
  CleanFlowPool: () => {
    get().setFlowPool({});
  },
  setPending: (isPending) => {
    set({ isPending });
  },
  resetFlow: ({ nodes, edges, viewport }) => {
    const currentFlow = useFlowsManagerStore.getState().currentFlow;
    let newEdges = cleanEdges(nodes, edges);
    const { inputs, outputs } = getInputsAndOutputs(nodes);
    set({
      nodes,
      edges: newEdges,
      flowState: undefined,
      inputs,
      outputs,
      hasIO: inputs.length > 0 || outputs.length > 0,
    });
    get().reactFlowInstance!.setViewport(viewport);
    if (currentFlow) {
      getFlowPool({ flowId: currentFlow.id }).then((flowPool) => {
        set({ flowPool: flowPool.data.vertex_builds });
      });
    }
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
  onNodesChange: (changes: NodeChange[]) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },
  onEdgesChange: (changes: EdgeChange[]) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },
  setNodes: (change) => {
    let newChange = typeof change === "function" ? change(get().nodes) : change;
    let newEdges = cleanEdges(newChange, get().edges);
    const { inputs, outputs } = getInputsAndOutputs(newChange);

    set({
      edges: newEdges,
      nodes: newChange,
      flowState: undefined,
      inputs,
      outputs,
      hasIO: inputs.length > 0 || outputs.length > 0,
    });

    const flowsManager = useFlowsManagerStore.getState();
    if (!get().isBuilding) {
      flowsManager.autoSaveCurrentFlow(
        newChange,
        newEdges,
        get().reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 }
      );
    }
  },
  setEdges: (change) => {
    let newChange = typeof change === "function" ? change(get().edges) : change;
    set({
      edges: newChange,
      flowState: undefined,
    });

    const flowsManager = useFlowsManagerStore.getState();
    if (!get().isBuilding) {
      flowsManager.autoSaveCurrentFlow(
        get().nodes,
        newChange,
        get().reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 }
      );
    }
  },
  setNode: (id: string, change: Node | ((oldState: Node) => Node)) => {
    let newChange =
      typeof change === "function"
        ? change(get().nodes.find((node) => node.id === id)!)
        : change;

    get().setNodes((oldNodes) =>
      oldNodes.map((node) => {
        if (node.id === id) {
          return newChange;
        }
        return node;
      })
    );
  },
  getNode: (id: string) => {
    return get().nodes.find((node) => node.id === id);
  },
  deleteNode: (nodeId) => {
    get().setNodes(
      get().nodes.filter((node) =>
        typeof nodeId === "string"
          ? node.id !== nodeId
          : !nodeId.includes(node.id)
      )
    );
  },
  deleteEdge: (edgeId) => {
    get().setEdges(
      get().edges.filter((edge) =>
        typeof edgeId === "string"
          ? edge.id !== edgeId
          : !edgeId.includes(edge.id)
      )
    );
  },
  paste: (selection, position) => {
    let minimumX = Infinity;
    let minimumY = Infinity;
    let idsMap = {};
    let newNodes: Node<NodeDataType>[] = get().nodes;
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

    selection.nodes.forEach((node: NodeType) => {
      // Generate a unique node ID
      let newId = getNodeId(node.data.type);
      idsMap[node.id] = newId;

      // Create a new node object
      const newNode: NodeType = {
        id: newId,
        type: "genericNode",
        position: {
          x: insidePosition.x + node.position!.x - minimumX,
          y: insidePosition.y + node.position!.y - minimumY,
        },
        data: {
          ...cloneDeep(node.data),
          id: newId,
        },
      };

      // Add the new node to the list of nodes in state
      newNodes = newNodes
        .map((node) => ({ ...node, selected: false }))
        .concat({ ...newNode, selected: false });
    });
    get().setNodes(newNodes);

    selection.edges.forEach((edge: Edge) => {
      let source = idsMap[edge.source];
      let target = idsMap[edge.target];
      const sourceHandleObject: sourceHandleType = scapeJSONParse(
        edge.sourceHandle!
      );
      let sourceHandle = scapedJSONStringfy({
        ...sourceHandleObject,
        id: source,
      });
      sourceHandleObject.id = source;

      edge.data.sourceHandle = sourceHandleObject;
      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!
      );
      let targetHandle = scapedJSONStringfy({
        ...targetHandleObject,
        id: target,
      });
      targetHandleObject.id = target;
      edge.data.targetHandle = targetHandleObject;
      let id = getHandleId(source, sourceHandle, target, targetHandle);
      newEdges = addEdge(
        {
          source,
          target,
          sourceHandle,
          targetHandle,
          id,
          data: cloneDeep(edge.data),
          style: { stroke: "#555" },
          className: "stroke-gray-900 ",
          selected: false,
        },
        newEdges.map((edge) => ({ ...edge, selected: false }))
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
        (node) => !nodesIdsSelected.includes(node.id)
      );
      const newEdges = get().edges.filter(
        (edge) => !edgesIdsSelected.includes(edge.id)
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

    let newEdges: Edge[] = [];
    get().setEdges((oldEdges) => {
      newEdges = addEdge(
        {
          ...connection,
          data: {
            targetHandle: scapeJSONParse(connection.targetHandle!),
            sourceHandle: scapeJSONParse(connection.sourceHandle!),
          },
          style: { stroke: "#555" },
          className: "stroke-foreground stroke-connection",
        },
        oldEdges
      );

      return newEdges;
    });
    useFlowsManagerStore
      .getState()
      .autoSaveCurrentFlow(
        get().nodes,
        newEdges,
        get().reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 }
      );
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
  buildFlow: async (nodeId?: string) => {
    get().setIsBuilding(true);
    const currentFlow = useFlowsManagerStore.getState().currentFlow;
    const setSuccessData = useAlertStore.getState().setSuccessData;
    const setErrorData = useAlertStore.getState().setErrorData;
    const setNoticeData = useAlertStore.getState().setNoticeData;
    function validateSubgraph(nodes: string[]) {
      const errors = validateNodes(
        get().nodes.filter((node) => nodes.includes(node.id)),
        get().edges
      );
      if (errors.length > 0) {
        setErrorData({
          title: MISSED_ERROR_ALERT,
          list: errors,
        });
        get().setIsBuilding(false);
        throw new Error("Invalid nodes");
      }
    }
    function handleBuildUpdate(
      vertexBuildData: VertexBuildTypeAPI,
      status: BuildStatus
    ) {
      if (vertexBuildData && vertexBuildData.inactive_vertices) {
        get().removeFromVerticesBuild(vertexBuildData.inactive_vertices);
      }
      get().addDataToFlowPool(vertexBuildData, vertexBuildData.id);
      useFlowStore.getState().updateBuildStatus([vertexBuildData.id], status);
    }
    await updateFlowInDatabase({
      data: {
        nodes: get().nodes,
        edges: get().edges,
        viewport: get().reactFlowInstance?.getViewport()!,
      },
      id: currentFlow!.id,
      name: currentFlow!.name,
      description: currentFlow!.description,
    });
    await buildVertices({
      flowId: currentFlow!.id,
      nodeId,
      onGetOrderSuccess: () => {
        setNoticeData({ title: "Running components" });
      },
      onBuildComplete: () => {
        if (nodeId) {
          setSuccessData({
            title: `${
              get().nodes.find((node) => node.id === nodeId)?.data.node
                ?.display_name
            } built successfully`,
          });
        } else {
          setSuccessData({ title: FLOW_BUILD_SUCCESS_ALERT });
        }
        get().setIsBuilding(false);
      },
      onBuildUpdate: handleBuildUpdate,
      onBuildError: (title, list, idList) => {
        useFlowStore.getState().updateBuildStatus(idList, BuildStatus.BUILT);
        setErrorData({ list, title });
      },
      onBuildStart: (idList) => {
        useFlowStore.getState().updateBuildStatus(idList, BuildStatus.BUILDING);
      },
      validateNodes: validateSubgraph,
    });
    get().revertBuiltStatusFromBuilding();
  },
  getFlow: () => {
    return {
      nodes: get().nodes,
      edges: get().edges,
      viewport: get().reactFlowInstance?.getViewport()!,
    };
  },
  updateVerticesBuild: (vertices: string[]) => {
    set({ verticesBuild: vertices });
  },
  verticesBuild: [],

  removeFromVerticesBuild: (vertices: string[]) => {
    set({
      verticesBuild: get().verticesBuild.filter(
        (vertex) => !vertices.includes(vertex)
      ),
    });
  },
  updateBuildStatus: (nodeIdList: string[], status: BuildStatus) => {
    const newFlowBuildStatus = { ...get().flowBuildStatus };
    nodeIdList.forEach((id) => {
      newFlowBuildStatus[id] = status;
    });
    set({ flowBuildStatus: newFlowBuildStatus });
  },
  revertBuiltStatusFromBuilding: () => {
    const newFlowBuildStatus = { ...get().flowBuildStatus };
    Object.keys(newFlowBuildStatus).forEach((id) => {
      if (newFlowBuildStatus[id] === BuildStatus.BUILDING) {
        newFlowBuildStatus[id] = BuildStatus.BUILT;
      }
    });
  },
}));

export default useFlowStore;
