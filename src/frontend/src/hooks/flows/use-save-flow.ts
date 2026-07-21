import type { ReactFlowJsonObject } from "@xyflow/react";
import { useTranslation } from "react-i18next";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
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
    const currentFlow = useFlowStore.getState().currentFlow;
    const currentSavedFlow = useFlowsManagerStore.getState().currentFlow;
    const requestedFlow = flow || currentFlow;
    const isPersistedFlowLocked =
      currentSavedFlow?.id === requestedFlow?.id &&
      currentSavedFlow?.locked === true;
    const isUnlockingPersistedFlow =
      isPersistedFlowLocked && requestedFlow?.locked === false;

    // Hydrating a flow can change client-only node metadata and the viewport.
    // Do not let those differences trigger saves while the persisted flow is
    // locked. Unlocking is handled separately below.
    if (isPersistedFlowLocked && !isUnlockingPersistedFlow) {
      return;
    }

    if (customStringify(requestedFlow) !== customStringify(currentSavedFlow)) {
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
          const updatePayload = {
            id,
            name,
            data: data!,
            description,
            folder_id,
            endpoint_name,
            locked,
          };
          // biome-ignore lint/suspicious/noExplicitAny: legacy
          const handleError = (e: any) => {
            const detail =
              e.response?.data?.detail || e.message || "Unknown error";
            setErrorData({
              title: t("errors.failedToSaveFlow"),
              list: [detail],
            });
            setSaveLoading(false);
            reject(e);
          };
          const persistFlow = () => {
            mutate(updatePayload, {
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
              onError: handleError,
            });
          };

          if (isUnlockingPersistedFlow) {
            mutate(
              { id, locked: false },
              {
                // Preserve any settings edits by applying them only after the
                // backend has committed the unlock-only request.
                onSuccess: persistFlow,
                onError: handleError,
              },
            );
          } else {
            persistFlow();
          }
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
