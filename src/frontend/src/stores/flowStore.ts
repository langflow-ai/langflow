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
import {
  cleanEdges,
  getHandleId,
  getNodeId,
  scapeJSONParse,
  scapedJSONStringfy,
} from "../utils/reactflowUtils";
import useFlowsManagerStore from "./flowsManagerStore";

// this is our useStore hook that we can use in our components to get parts of the store and call actions
const useFlowStore = create<FlowStoreType>((set, get) => ({
  sseData: {},
  flowState: undefined,
  nodes: [],
  edges: [],
  isBuilding: false,
  isPending: false,
  isBuilt: false,
  reactFlowInstance: null,
  lastCopiedSelection: null,
  setPending: (isPending) => {
    set({ isPending });
  },
  resetFlow: ({ nodes, edges, viewport }) => {
    set({
      nodes,
      edges,
      flowState: undefined,
      sseData: {},
      isBuilt: false,
    });
    get().reactFlowInstance!.setViewport(viewport);
  },
  updateSSEData: (sseData) => {
    set((state) => ({ sseData: { ...state.sseData, ...sseData } }));
  },
  setIsBuilding: (isBuilding) => {
    set({ isBuilding });
  },
  setIsBuilt: (isBuilt) => {
    set({ isBuilt });
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
      isBuilt: false,
      sseData: {},
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
      isBuilt: false,
      sseData: {},
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
    get().setEdges(newEdges);
  },
  setLastCopiedSelection: (newSelection) => {
    set({ lastCopiedSelection: newSelection });
  },
  cleanFlow: () => {
    set({
      nodes: [],
      edges: [],
      flowState: undefined,
      sseData: {},
      isBuilt: false,
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
}));

export default useFlowStore;
