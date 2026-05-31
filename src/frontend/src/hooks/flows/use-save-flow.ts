import type { ReactFlowJsonObject } from "@xyflow/react";
import { useTranslation } from "react-i18next";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import { syncSavedFlowStateFromCanvas } from "@/hooks/flows/flow-operation-adapter";
import { buildUpdateMetadataOperation } from "@/hooks/flows/flow-operation-diff";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";

const useSaveFlow = () => {
  const { t } = useTranslation();
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);

  const { mutate: getFlow } = useGetFlow();
  const { mutate } = usePatchUpdateFlow();

  const saveFlow = async (flow?: FlowType): Promise<void> => {
    const flowStore = useFlowStore.getState();
    const currentFlow = flowStore.currentFlow;
    const currentSavedFlow = useFlowsManagerStore.getState().currentFlow;

    if (flowStore.collaborationOperationMode) {
      setSaveLoading(true);
      try {
        const flowToSave = flow ?? currentFlow;
        const metadataOperation = buildUpdateMetadataOperation(
          currentSavedFlow?.data as Record<string, unknown> | null | undefined,
          flowToSave?.data as Record<string, unknown> | null | undefined,
        );
        if (metadataOperation) {
          flowStore.onCollaborationOperations?.([metadataOperation]);
        }
        if (flowStore.flushCollaborationSave) {
          await flowStore.flushCollaborationSave();
        } else {
          syncSavedFlowStateFromCanvas();
        }
        setSaveLoading(false);
        return;
      } catch (error) {
        setSaveLoading(false);
        const detail =
          error instanceof Error
            ? error.message
            : "Unknown collaboration save error";
        setErrorData({
          title: t("errors.failedToSaveFlow"),
          list: [detail],
        });
        throw error;
      }
    }

    if (
      customStringify(flow || currentFlow) !== customStringify(currentSavedFlow)
    ) {
      setSaveLoading(true);

      const flowData = currentFlow?.data;
      const nodes = useFlowStore.getState().nodes;
      const edges = useFlowStore.getState().edges;
      const reactFlowInstance = useFlowStore.getState().reactFlowInstance;

      return new Promise<void>((resolve, reject) => {
        if (currentFlow) {
          flow = flow || {
            ...currentFlow,
            data: {
              ...flowData,
              nodes,
              edges,
              viewport: reactFlowInstance?.getViewport() ?? {
                zoom: 1,
                x: 0,
                y: 0,
              },
            },
          };
        }

        if (flow) {
          if (!flow?.data) {
            getFlow(
              { id: flow!.id },
              {
                onSuccess: (flowResponse) => {
                  flow!.data = flowResponse.data as ReactFlowJsonObject<
                    AllNodeType,
                    EdgeType
                  >;
                },
              },
            );
          }

          const {
            id,
            name,
            data,
            description,
            folder_id,
            endpoint_name,
            locked,
          } = flow;
          mutate(
            {
              id,
              name,
              data: data!,
              description,
              folder_id,
              endpoint_name,
              locked,
            },
            {
              onSuccess: (updatedFlow) => {
                const flows = useFlowsManagerStore.getState().flows;
                setSaveLoading(false);
                if (flows) {
                  // updates flow in state
                  setFlows(
                    flows.map((flow) => {
                      if (flow.id === updatedFlow.id) {
                        return updatedFlow;
                      }
                      return flow;
                    }),
                  );
                  // Only update useFlowStore.currentFlow when on the flow page.
                  // When saving from the list page (e.g., renaming via settings modal),
                  // setting this would leave stale unprocessed flow data in the store,
                  // causing a crash when the user later navigates to the flow page.
                  if (useFlowStore.getState().onFlowPage) {
                    setCurrentFlow(updatedFlow);
                  }
                  resolve();
                } else {
                  setErrorData({
                    title: t("errors.failedToSaveFlow"),
                    list: [t("errors.flowsVariableUndefined")],
                  });
                  reject(new Error("Flows variable undefined"));
                }
              },
              // biome-ignore lint/suspicious/noExplicitAny: legacy
              onError: (e: any) => {
                const detail =
                  e.response?.data?.detail || e.message || "Unknown error";
                setErrorData({
                  title: t("errors.failedToSaveFlow"),
                  list: [detail],
                });
                setSaveLoading(false);
                reject(e);
              },
            },
          );
        } else {
          setErrorData({
            title: t("errors.failedToSaveFlow"),
            list: [t("errors.flowNotFound")],
          });
          reject(new Error("Flow not found"));
        }
      });
    }
  };

  return saveFlow;
};

export default useSaveFlow;
