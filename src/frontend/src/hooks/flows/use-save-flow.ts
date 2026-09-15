import type { ReactFlowJsonObject } from "@xyflow/react";
import { useTranslation } from "react-i18next";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { extractApiErrorCode, extractApiErrorMessages } from "@/utils/apiError";
import { customStringify } from "@/utils/reactflowUtils";

// Opt-out for callers that recover from a save failure themselves.
export type SaveFlowOptions = { suppressErrorToast?: boolean };

const useSaveFlow = () => {
  const { t } = useTranslation();
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);

  const { mutate: getFlow } = useGetFlow();
  const { mutate } = usePatchUpdateFlow();

  const saveFlow = async (
    flow?: FlowType,
    options?: SaveFlowOptions,
  ): Promise<void> => {
    const currentFlow = useFlowStore.getState().currentFlow;
    const currentSavedFlow = useFlowsManagerStore.getState().currentFlow;
    const requestedFlow = flow || currentFlow;
    const isCurrentEditorFlowLocked =
      currentFlow?.id === requestedFlow?.id && currentFlow?.locked === true;
    const isPersistedFlowLocked =
      isCurrentEditorFlowLocked ||
      (currentSavedFlow?.id === requestedFlow?.id &&
        currentSavedFlow?.locked === true);
    const isUnlockingPersistedFlow =
      isPersistedFlowLocked && requestedFlow?.locked === false;

    // Hydrating a flow can change client-only node metadata and the viewport.
    // Do not let those differences trigger saves while the persisted flow is
    // locked. Unlocking is handled separately below.
    if (isPersistedFlowLocked && !isUnlockingPersistedFlow) {
      return;
    }

    const reportSaveError = (detail: string) => {
      if (options?.suppressErrorToast) return;
      setErrorData({ title: t("errors.failedToSaveFlow"), list: [detail] });
    };

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
            edit_revision,
            name,
            data,
            description,
            folder_id,
            endpoint_name,
            locked,
          } = flow;
          const persistedFlowForScope =
            currentSavedFlow?.id === id
              ? currentSavedFlow
              : useFlowsManagerStore
                  .getState()
                  .flows?.find((savedFlow) => savedFlow.id === id);
          const providerScopeChanged =
            persistedFlowForScope !== undefined &&
            persistedFlowForScope.folder_id !== folder_id;
          const observedEditRevision =
            edit_revision ?? persistedFlowForScope?.edit_revision;
          if (typeof observedEditRevision !== "number") {
            reportSaveError(t("errors.workflowRevisionUnavailable"));
            setSaveLoading(false);
            reject(new Error(t("errors.workflowRevisionUnavailable")));
            return;
          }
          const updatePayload = {
            id,
            name,
            data: data!,
            description,
            folder_id,
            endpoint_name,
            locked,
            ...(providerScopeChanged && { providerScopeChanged: true }),
          };
          // biome-ignore lint/suspicious/noExplicitAny: legacy
          const handleError = (e: any) => {
            const code = extractApiErrorCode(e);
            const status = e.response?.status;
            const detail =
              status === 412 || code === "RESOURCE_CHANGED"
                ? t("errors.flowChangedBeforeSave")
                : status === 403
                  ? t("errors.flowEditingAccessChanged")
                  : extractApiErrorMessages(e)[0];
            reportSaveError(detail);
            setSaveLoading(false);
            reject(e);
          };
          const persistFlow = (observedRevision = observedEditRevision) => {
            mutate(
              { ...updatePayload, edit_revision: observedRevision },
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
                    //
                    // Preserve edits made while this save was pending, but
                    // advance their observed revision after our successful write.
                    // Otherwise the next save conflicts with our own response.
                    const liveState = useFlowStore.getState();
                    const graphUnchanged =
                      liveState.nodes === nodes && liveState.edges === edges;
                    if (
                      liveState.onFlowPage &&
                      liveState.currentFlow?.id === updatedFlow.id
                    ) {
                      setCurrentFlow(
                        graphUnchanged
                          ? updatedFlow
                          : {
                              ...liveState.currentFlow,
                              edit_revision: updatedFlow.edit_revision,
                            },
                      );
                    }
                    resolve();
                  } else {
                    reportSaveError(t("errors.flowsVariableUndefined"));
                    reject(new Error("Flows variable undefined"));
                  }
                },
                onError: handleError,
              },
            );
          };

          if (isUnlockingPersistedFlow) {
            mutate(
              { id, edit_revision: observedEditRevision, locked: false },
              {
                // Preserve any settings edits by applying them only after the
                // backend has committed the unlock-only request.
                onSuccess: (unlockedFlow) =>
                  persistFlow(unlockedFlow.edit_revision),
                onError: handleError,
              },
            );
          } else {
            persistFlow();
          }
        } else {
          reportSaveError(t("errors.flowNotFound"));
          reject(new Error("Flow not found"));
        }
      });
    }
  };

  return saveFlow;
};

export default useSaveFlow;
