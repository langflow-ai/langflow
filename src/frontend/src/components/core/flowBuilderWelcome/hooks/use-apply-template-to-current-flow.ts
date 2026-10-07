import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { getUserScopedDuplicateName } from "@/utils/flow-naming";
import {
  findStarterTemplate,
  type StarterTemplateNameKey,
} from "../helpers/find-starter-template";

const MAX_NAME_CONFLICT_RETRIES = 3;

type ApiErrorLike = {
  response?: { status?: number; data?: { detail?: unknown } };
  message?: string;
};

function asApiError(error: unknown): ApiErrorLike {
  return (error ?? {}) as ApiErrorLike;
}

function isFlowNameConflict(error: unknown): boolean {
  const { response } = asApiError(error);
  const detail = response?.data?.detail;
  return (
    response?.status === 400 &&
    typeof detail === "string" &&
    detail.toLowerCase() === "name must be unique"
  );
}

function getErrorDetail(error: unknown): string {
  const { response, message } = asApiError(error);
  const detail = response?.data?.detail;
  return typeof detail === "string" ? detail : (message ?? "Unknown error");
}

// Swaps the current (empty, welcome-created) flow's data with a starter
// template in place. Returns false when the template isn't loaded yet.
export function useApplyTemplateToCurrentFlow() {
  const { t } = useTranslation();
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const requestFitView = useFlowStore((state) => state.requestFitView);
  const examples = useFlowsManagerStore((state) => state.examples);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  // Use the manager store's setCurrentFlow so resetFlow (and syncNodeTranslations)
  // runs, ensuring component names are shown in the active language immediately.
  const setCurrentFlowInManager = useFlowsManagerStore(
    (state) => state.setCurrentFlow,
  );
  const saveFlow = useSaveFlow();

  return useCallback(
    (nameKey: StarterTemplateNameKey, onFitted?: () => void): boolean => {
      const template = findStarterTemplate(examples, nameKey);
      const templateData = template?.data;
      if (!template || !templateData) return false;

      if (currentFlow) {
        // Feeding backend-rejected names back as pseudo-flows lets the same
        // versioning logic hand out the next candidate.
        const rejectedNames: string[] = [];
        const nextCandidateName = () =>
          getUserScopedDuplicateName(
            { ...currentFlow, name: template.name },
            [
              ...(flows ?? []),
              ...rejectedNames.map((name, index) => ({
                id: `rejected-${index}`,
                name,
              })),
            ],
            examples ?? [],
          );

        const buildFlow = (name: string): FlowType => ({
          ...currentFlow,
          name,
          data: {
            nodes: templateData.nodes ?? [],
            edges: templateData.edges ?? [],
            viewport: currentFlow.data?.viewport ?? { x: 0, y: 0, zoom: 1 },
          },
        });

        // saveFlow bails out when the payload already matches the manager
        // store, so the request has to be issued before the optimistic swap.
        const persist = async (attempt: number): Promise<void> => {
          const candidate = buildFlow(nextCandidateName());
          const persisted = saveFlow(candidate, { suppressErrorToast: true });
          setCurrentFlowInManager(candidate);
          try {
            await persisted;
          } catch (error) {
            if (
              isFlowNameConflict(error) &&
              attempt < MAX_NAME_CONFLICT_RETRIES
            ) {
              rejectedNames.push(candidate.name);
              return persist(attempt + 1);
            }
            setErrorData({
              title: t("errors.failedToSaveFlow"),
              list: [getErrorDetail(error)],
            });
            // Only roll back if the user hasn't switched to a different flow.
            const latest = useFlowsManagerStore.getState().currentFlow;
            if (latest?.id === candidate.id) {
              setCurrentFlowInManager(currentFlow);
            }
          }
        };

        void persist(0);
      } else {
        // No flow context yet — update the canvas directly as a fallback.
        setNodes(templateData.nodes ?? []);
        setEdges(templateData.edges ?? []);
      }

      // A template's nodes measure across several ResizeObserver batches, and a
      // fit that runs before they all have dimensions silently drops the ones
      // still pending — the flow would open framed around a subset. The canvas
      // fits once the graph is fully measured and then uncovers itself through
      // `onFitted`; uncovering returns the sidebar to the layout and narrows
      // the canvas, which `useFitViewWhenMeasured` corrects on its own.
      requestFitView(() => onFitted?.());
      return true;
    },
    [
      examples,
      flows,
      currentFlow,
      setNodes,
      setEdges,
      setCurrentFlowInManager,
      setErrorData,
      saveFlow,
      requestFitView,
      t,
    ],
  );
}
