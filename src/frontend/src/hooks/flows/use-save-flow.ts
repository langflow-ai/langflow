import type { ReactFlowJsonObject } from "@xyflow/react";
import { useTranslation } from "react-i18next";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowConflictStore, {
  type ConflictDetail,
} from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";
import {
  attachTheirFlow,
  fetchAndAdoptServerVersion,
  registerConflictState,
} from "./conflict-actions";
import { FlowSaveBlockedError } from "./save-blocked-error";
import { buildFlowUpdatePayload } from "./save-payload";

// Opt-out for callers that recover from a save failure themselves.
export type SaveFlowOptions = { suppressErrorToast?: boolean };

const useSaveFlow = () => {
  const { t } = useTranslation();
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);

  const { mutate: getFlow } = useGetFlow();
  const { mutate } = usePatchUpdateFlow();

  const registerConflict = (flowId: string, detail: ConflictDetail) => {
    const currentUserId = useAuthStore.getState().userData?.id ?? null;
    const authorId = detail.modified_by?.id ?? null;
    const authorName = detail.modified_by?.username ?? null;

    // Nothing of mine is on the canvas, so there is nothing to resolve. Raising a
    // banner here produced a dialog with no changes on either side and no honest
    // exit; taking their version is the whole answer. It is said out loud, because
    // the refused request still carried something the person typed -- a rename, a
    // lock, an endpoint -- and adopting their version drops it. That used to
    // disappear with no message at all.
    if (!useFlowStore.getState().userEditedSinceLoad) {
      setNoticeData({
        title: authorName
          ? t("multiEdit.notice.changeNotApplied", { name: authorName })
          : t("multiEdit.notice.changeNotAppliedUnknown"),
      });
      void fetchAndAdoptServerVersion(flowId);
      return;
    }
    // Registering also persists the draft, so refused work survives a reload no
    // matter which path noticed the conflict.
    registerConflictState({
      flowId,
      authorId,
      authorName,
      modifiedAt: detail.modified_at ?? null,
      expectedToken: detail.expected_version_token ?? null,
      currentToken: detail.current_version_token ?? null,
      currentUserId,
    });

    // Fetched now, not when the dialog opens: a third save in between would make
    // the diff describe a version this conflict was never about.
    void attachTheirFlow(flowId);
  };

  const saveFlow = async (
    flow?: FlowType,
    options?: SaveFlowOptions,
  ): Promise<void> => {
    const currentFlow = useFlowStore.getState().currentFlow;
    const currentSavedFlow = useFlowsManagerStore.getState().currentFlow;
    const requestedFlow = flow || currentFlow;

    // Saving to the original is over once refused; retrying can only fail forever.
    const conflictState = useFlowConflictStore.getState();
    const requestedId = requestedFlow?.id;
    if (
      requestedId &&
      (conflictState.conflict?.flowId === requestedId ||
        conflictState.abandonedFlowIds.has(requestedId))
    ) {
      throw new FlowSaveBlockedError(requestedId);
    }
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

          const { id } = flow;
          // The baseline is the last applied server response, never the canvas,
          // which can hold a token from a response this save has not adopted.
          const updatePayload = buildFlowUpdatePayload({
            flow,
            persisted:
              currentSavedFlow?.id === id ? currentSavedFlow : undefined,
            flows: useFlowsManagerStore.getState().flows,
            live: currentFlow?.id === id ? { nodes, edges } : undefined,
            userEdited: useFlowStore.getState().userEditedSinceLoad,
          });
          // biome-ignore lint/suspicious/noExplicitAny: legacy
          const handleError = (e: any) => {
            const detail = e.response?.data?.detail;
            if (
              e.response?.status === 409 &&
              detail?.code === "flow_version_conflict"
            ) {
              // Not an error the user can retry away: the flow moved on without
              // them, so the banner takes over and the toast would only add noise.
              registerConflict(id, detail);
              setSaveLoading(false);
              reject(e);
              return;
            }
            reportSaveError(detail || e.message || "Unknown error");
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
                  //
                  // And only when the canvas still holds the graph this request
                  // carried. `currentFlow` is the baseline the next autosave
                  // diffs against, so adopting the response of a save that
                  // started before an edit makes that edit look persisted and
                  // the follow-up save is skipped — the edit is lost. The
                  // store swaps these arrays on every change, so identity is
                  // an exact "nothing moved while we were away" check.
                  const liveState = useFlowStore.getState();
                  const graphUnchanged =
                    liveState.nodes === nodes && liveState.edges === edges;
                  if (liveState.onFlowPage && graphUnchanged) {
                    setCurrentFlow(updatedFlow);
                  }
                  resolve();
                } else {
                  reportSaveError(t("errors.flowsVariableUndefined"));
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
          reportSaveError(t("errors.flowNotFound"));
          reject(new Error("Flow not found"));
        }
      });
    }
  };

  return saveFlow;
};

export default useSaveFlow;
