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
import {
  NodeDataType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import { FlowStoreType } from "../types/zustand/flow";
import { buildVertices } from "../utils/buildUtils";
import {
  cleanEdges,
  getHandleId,
  getNodeId,
  isInputNode,
  isOutputNode,
  scapeJSONParse,
  scapedJSONStringfy,
} from "../utils/reactflowUtils";
import useAlertStore from "./alertStore";
import useFlowsManagerStore from "./flowsManagerStore";

// this is our useStore hook that we can use in our components to get parts of the store and call actions
const useFlowStore = create<FlowStoreType>((set, get) => ({
  flowState: undefined,
  nodes: [],
  edges: [],
  isBuilding: false,
  isPending: false,
  reactFlowInstance: null,
  lastCopiedSelection: null,
  flowPool: {},
  outputTypes: [],
  inputTypes: [],
  inputIds: [],
  outputIds: [],
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
  CleanFlowPool: () => {
    get().setFlowPool({});
  },
  setPending: (isPending) => {
    set({ isPending });
  },
  resetFlow: ({ nodes, edges, viewport }) => {
    set({
      nodes,
      edges,
      flowState: undefined,
    });
    get().reactFlowInstance!.setViewport(viewport);
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

    set({
      edges: newEdges,
      nodes: newChange,
      flowState: undefined,
    });

    const flowsManager = useFlowsManagerStore.getState();

    flowsManager.autoSaveCurrentFlow(
      newChange,
      newEdges,
      get().reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 }
    );
  },
  setEdges: (change) => {
    let newChange = typeof change === "function" ? change(get().edges) : change;

    set({
      edges: newChange,
      flowState: undefined,
    });

    const flowsManager = useFlowsManagerStore.getState();

    flowsManager.autoSaveCurrentFlow(
      get().nodes,
      newChange,
      get().reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 }
    );
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
  checkInputAndOutput: () => {
    let has_input = false;
    let has_output = false;
    const nodes = get().nodes;
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isInputNode(nodeData)) {
        has_input = true;
      }
      if (isOutputNode(nodeData)) {
        has_output = true;
      }
    });
    return has_input && has_output;
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
    set({ nodes: newNodes });

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
          className:
            targetHandleObject.type === "Text"
              ? "stroke-gray-800 "
              : "stroke-gray-900 ",
          animated: targetHandleObject.type === "Text",
          selected: false,
        },
        newEdges.map((edge) => ({ ...edge, selected: false }))
      );
    });
    set({ edges: newEdges });
  },
  setLastCopiedSelection: (newSelection) => {
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
          className:
            ((scapeJSONParse(connection.targetHandle!) as targetHandleType)
              .type === "Text"
              ? "stroke-foreground "
              : "stroke-foreground ") + " stroke-connection",
          animated:
            (scapeJSONParse(connection.targetHandle!) as targetHandleType)
              .type === "Text",
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
  getInputTypes: () => {
    let inputType: string[] = [];
    const nodes = get().nodes;
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isInputNode(nodeData)) {
        // TODO remove count and ramdom key from type before pushing
        inputType.push(nodeData.type);
      }
    });
    set({ inputTypes: inputType });
    return inputType;
  },
  getOutputTypes: () => {
    let outputType: string[] = [];
    const nodes = get().nodes;
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isOutputNode(nodeData)) {
        outputType.push(nodeData.type);
      }
    });
    set({ outputTypes: outputType });
    return outputType;
  },
  getInputIds: () => {
    let inputIds: string[] = [];
    const nodes = get().nodes;
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isInputNode(nodeData)) {
        inputIds.push(nodeData.id);
      }
    });
    set({ inputIds });
    return inputIds;
  },
  getOutputIds: () => {
    let outputIds: string[] = [];
    const nodes = get().nodes;

    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isOutputNode(nodeData)) {
        outputIds.push(nodeData.id);
      }
    });
    set({ outputIds });
    return outputIds;
  },
  buildFlow: async (nodeId?: string) => {
    function handleBuildUpdate(data: any) {
      get().addDataToFlowPool(data.data[data.id], data.id);
    }
    const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
    const setSuccessData = useAlertStore((state) => state.setSuccessData);
    const setErrorData = useAlertStore((state) => state.setErrorData);
    return buildVertices({
      flow: {
        data: {
          edges: get().edges,
          nodes: get().nodes,
          viewport: get().reactFlowInstance?.getViewport()!,
        },
        description: currentFlow?.description!,
        id: currentFlow?.id!,
        name: currentFlow?.name!,
      },
      nodeId,
      onBuildComplete: () => {
        if (nodeId) {
          setSuccessData({ title: `${nodeId} built successfully` });
        } else {
          setSuccessData({ title: `Flow built successfully` });
        }
      },
      onBuildUpdate: handleBuildUpdate,
      onBuildError: (title, list) => {
        setErrorData({ list, title });
      },
    });
  },
  getFlow: () => {
    return {
      nodes: get().nodes,
      edges: get().edges,
      viewport: get().reactFlowInstance?.getViewport()!,
    };
  },
}));

export default useFlowStore;
