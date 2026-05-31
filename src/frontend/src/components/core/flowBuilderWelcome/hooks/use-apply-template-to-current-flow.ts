import { cloneDeep } from "lodash";
import { useCallback } from "react";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import {
  buildGraphDiffOperations,
  buildInverseFlowOperations,
} from "@/hooks/flows/flow-operation-diff";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { getFolderScopedDuplicateName } from "@/utils/flow-naming";
import {
  findStarterTemplate,
  type StarterTemplateNameKey,
} from "../helpers/find-starter-template";

// Swaps the current (empty, welcome-created) flow's data with a starter
// template in place. Returns false when the template isn't loaded yet.
export function useApplyTemplateToCurrentFlow() {
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const examples = useFlowsManagerStore((state) => state.examples);
  const flows = useFlowsManagerStore((state) => state.flows);
  const saveFlow = useSaveFlow();

  return useCallback(
    (nameKey: StarterTemplateNameKey, onFitted?: () => void): boolean => {
      const template = findStarterTemplate(examples, nameKey);
      if (!template?.data) return false;
      const templateNodes = cloneDeep(template.data.nodes ?? []);
      const templateEdges = cloneDeep(template.data.edges ?? []);
      const flowStore = useFlowStore.getState();

      if (
        flowStore.collaborationOperationMode &&
        flowStore.onCollaborationOperations
      ) {
        const previousNodes = flowStore.nodes;
        const previousEdges = flowStore.edges;
        const previousData = flowStore.currentFlow?.data as
          | Record<string, unknown>
          | undefined;
        setNodes(templateNodes, { skipCollaborationEmit: true });
        setEdges(templateEdges, { skipCollaborationEmit: true });
        const operations = buildGraphDiffOperations(
          previousNodes,
          previousEdges,
          templateNodes,
          templateEdges,
        );
        if (operations.length > 0) {
          flowStore.onCollaborationOperations(operations, {
            historyEntry: {
              forwardOps: cloneDeep(operations),
              inverseOps: buildInverseFlowOperations(
                previousNodes,
                previousEdges,
                previousData,
                operations,
              ),
            },
          });
        }
      } else {
        setNodes(templateNodes);
        setEdges(templateEdges);
      }

      if (currentFlow) {
        const renamedFlow: FlowType = {
          ...currentFlow,
          name: getFolderScopedDuplicateName(
            { ...currentFlow, name: template.name },
            flows ?? [],
            currentFlow.folder_id,
          ),
          data: {
            nodes: templateNodes,
            edges: templateEdges,
            viewport: currentFlow.data?.viewport ?? { x: 0, y: 0, zoom: 1 },
          },
        };
        setCurrentFlow(renamedFlow);
        // Roll back the optimistic rename on failure (saveFlow toasts its own error).
        void saveFlow(renamedFlow).catch(() => setCurrentFlow(currentFlow));
      }
      // Why this dance:
      //   1. ReactFlow can only compute the correct viewport AFTER the new
      //      nodes have rendered AND been measured — node widths/heights are
      //      read from the DOM, not the data.
      //   2. So we wait two rAFs: first for React to commit setNodes/setEdges,
      //      then for ReactFlow to lay out the new nodes.
      //   3. We call `fitView` with NO `duration` so the camera SNAPS to
      //      the right viewport — the welcome overlay is still covering the
      //      canvas at this point, so the snap is invisible to the user.
      //   4. `onFitted` (the welcome's `close`) runs on the next frame,
      //      revealing an already-fit canvas instead of an animated camera
      //      flying into place.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          reactFlowInstance?.fitView({
            padding: { left: "20px", right: "20px", top: "80px" },
          });
          requestAnimationFrame(() => onFitted?.());
        });
      });
      return true;
    },
    [
      examples,
      flows,
      currentFlow,
      setNodes,
      setEdges,
      setCurrentFlow,
      saveFlow,
      reactFlowInstance,
    ],
  );
}
