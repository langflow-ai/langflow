import { useCallback } from "react";
import useSaveFlow from "@/hooks/flows/use-save-flow";
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
      setNodes(template.data.nodes ?? []);
      setEdges(template.data.edges ?? []);

      if (currentFlow) {
        const renamedFlow: FlowType = {
          ...currentFlow,
          name: getFolderScopedDuplicateName(
            { ...currentFlow, name: template.name },
            flows ?? [],
            currentFlow.folder_id,
          ),
          data: {
            nodes: template.data.nodes ?? [],
            edges: template.data.edges ?? [],
            viewport: currentFlow.data?.viewport ?? { x: 0, y: 0, zoom: 1 },
          },
        };
        setCurrentFlow(renamedFlow);
        // Roll back the optimistic rename on failure (saveFlow toasts its own error).
        void saveFlow(renamedFlow).catch(() => setCurrentFlow(currentFlow));
      }
      // fitView reads node sizes from the DOM: wait two rAFs for ReactFlow to
      // commit/measure, then snap (no duration) while the overlay still covers it.
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
