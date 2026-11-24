import { cloneDeep } from "lodash";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";

/**
 * Adopts a server version onto the canvas as well as the baseline.
 *
 * ``adoptServerVersion`` alone moves only the baseline, which is right when the
 * canvas is about to be reloaded anyway. After an overwrite it is not: the canvas
 * still holds the author's own graph, so any change they took from the other
 * person would be missing from the screen *and* would be written back out by the
 * next autosave, silently undoing the merge they just chose.
 *
 * The save is suppressed because this graph came from the server -- writing it
 * straight back would mark a freshly resolved flow as edited again.
 */
export const adoptServerVersionOnCanvas = (serverFlow: FlowType): void => {
  const adopted = cloneDeep(serverFlow);
  processFlows([adopted]);
  useFlowsManagerStore.getState().setCurrentFlow(adopted);

  const graph = adopted.data;
  if (!graph) return;
  const flowState = useFlowStore.getState();
  flowState.setNodes(graph.nodes ?? [], { autoSave: false });
  flowState.setEdges(graph.edges ?? [], { autoSave: false });
  useFlowStore.setState({ userEditedSinceLoad: false });
};
