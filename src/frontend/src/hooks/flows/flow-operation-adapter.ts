import { cloneDeep } from "lodash";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import type { FlowOperation } from "@/types/flow-operations";
import { cleanEdges } from "@/utils/reactflowUtils";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { coalesceDeleteIds } from "./flow-operation-diff";

export type { FlowMutationOptions } from "@/types/flow-operations";
export {
  buildGraphDiffOperations,
  buildInverseFlowOperations,
  buildUpdateMetadataOperation,
  buildUpdateNodesOperation,
  collectFlowOperationTouches,
  flowOperationTouchesIntersect,
} from "./flow-operation-diff";

function applyDeleteNodes(
  nodes: AllNodeType[],
  edges: EdgeType[],
  ids: string[],
): { nodes: AllNodeType[]; edges: EdgeType[] } {
  const nodeIds = new Set(coalesceDeleteIds(ids));
  const nextNodes = nodes.filter((node) => !nodeIds.has(node.id));
  const nextEdges = edges.filter(
    (edge) => !nodeIds.has(edge.source) && !nodeIds.has(edge.target),
  );
  return { nodes: nextNodes, edges: nextEdges };
}

function applyDeleteEdges(edges: EdgeType[], ids: string[]): EdgeType[] {
  const edgeIds = new Set(coalesceDeleteIds(ids));
  return edges.filter((edge) => !edgeIds.has(edge.id));
}

export function applyFlowOperationsLocally(
  nodes: AllNodeType[],
  edges: EdgeType[],
  operations: FlowOperation[],
): { nodes: AllNodeType[]; edges: EdgeType[] } {
  let nextNodes = cloneDeep(nodes);
  let nextEdges = cloneDeep(edges);

  for (const operation of operations) {
    switch (operation.type) {
      case "add_nodes": {
        const existingIds = new Set(nextNodes.map((node) => node.id));
        for (const node of operation.nodes) {
          if (!existingIds.has(node.id)) {
            nextNodes.push(cloneDeep(node));
            existingIds.add(node.id);
          }
        }
        break;
      }
      case "update_nodes": {
        const nodeMap = new Map(nextNodes.map((node) => [node.id, node]));
        for (const node of operation.nodes) {
          if (nodeMap.has(node.id)) {
            nodeMap.set(node.id, cloneDeep(node));
          }
        }
        nextNodes = Array.from(nodeMap.values());
        break;
      }
      case "delete_nodes": {
        const deleted = applyDeleteNodes(nextNodes, nextEdges, operation.ids);
        nextNodes = deleted.nodes;
        nextEdges = deleted.edges;
        break;
      }
      case "add_edges": {
        const existingIds = new Set(nextEdges.map((edge) => edge.id));
        for (const edge of operation.edges) {
          if (!existingIds.has(edge.id)) {
            nextEdges.push(cloneDeep(edge));
            existingIds.add(edge.id);
          }
        }
        break;
      }
      case "delete_edges": {
        nextEdges = applyDeleteEdges(nextEdges, operation.ids);
        break;
      }
      case "update_metadata":
        break;
      default:
        break;
    }
  }

  const cleaned = cleanEdges(nextNodes, nextEdges);
  return { nodes: nextNodes, edges: cleaned.edges };
}

export function applyFlowOperationsToStore(operations: FlowOperation[]): void {
  const store = useFlowStore.getState();
  const metadataOps = operations.filter(
    (operation) => operation.type === "update_metadata",
  );
  const graphOps = operations.filter(
    (operation) => operation.type !== "update_metadata",
  );

  const { nodes, edges } = applyFlowOperationsLocally(
    store.nodes,
    store.edges,
    graphOps,
  );

  const { inputs, outputs } = getInputsAndOutputs(nodes);
  useFlowStore.setState({ isApplyingRemoteOperations: true });
  try {
    useFlowStore.setState({
      nodes,
      edges,
      flowState: undefined,
      inputs,
      outputs,
      hasIO: inputs.length > 0 || outputs.length > 0,
    });
    useFlowStore.getState().updateCurrentFlow({ nodes, edges });

    const currentFlow = useFlowStore.getState().currentFlow;
    if (metadataOps.length > 0 && currentFlow?.data) {
      const nextData = { ...currentFlow.data };
      for (const operation of metadataOps) {
        if (operation.type !== "update_metadata") {
          continue;
        }
        for (const [key, value] of Object.entries(operation.fields)) {
          if (key === "nodes" || key === "edges") {
            continue;
          }
          nextData[key] = value;
        }
        for (const key of operation.delete_keys ?? []) {
          if (key === "nodes" || key === "edges") {
            continue;
          }
          delete nextData[key];
        }
      }
      useFlowStore.getState().setCurrentFlow({
        ...currentFlow,
        data: {
          ...nextData,
          nodes,
          edges,
        },
      });
    }
  } finally {
    useFlowStore.setState({ isApplyingRemoteOperations: false });
  }
}

export function applyRemoteFlowOperations(operations: FlowOperation[]): void {
  applyFlowOperationsToStore(operations);
  useFlowsManagerStore.getState().clearUndoRedoHistory?.();
}

export function syncSavedFlowStateFromCanvas(): void {
  const flowStore = useFlowStore.getState();
  const currentFlow = flowStore.currentFlow;
  if (!currentFlow) {
    return;
  }

  const viewport = flowStore.reactFlowInstance?.getViewport() ??
    currentFlow.data?.viewport ?? {
      x: 0,
      y: 0,
      zoom: 1,
    };

  const updatedFlow: FlowType = {
    ...currentFlow,
    data: {
      ...currentFlow.data,
      nodes: flowStore.nodes,
      edges: flowStore.edges,
      viewport,
    },
  };

  flowStore.setCurrentFlow(updatedFlow);

  const flows = useFlowsManagerStore.getState().flows;
  if (!flows) {
    return;
  }

  useFlowsManagerStore
    .getState()
    .setFlows(
      flows.map((flow) => (flow.id === updatedFlow.id ? updatedFlow : flow)),
    );

  if (flowStore.onFlowPage) {
    useFlowsManagerStore.getState().setCurrentFlow(updatedFlow);
  }
}
