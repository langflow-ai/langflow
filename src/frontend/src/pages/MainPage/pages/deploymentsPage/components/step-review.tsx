import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { UNKNOWN_FLOW_NAME } from "../types";
import { ReviewDetachingSection } from "./step-review/review-detaching-section";
import { ReviewFlowConfigCard } from "./step-review/review-flow-config-card";
import { ReviewSummaryCard } from "./step-review/review-summary-card";
import { buildReviewFlows } from "./step-review/utils";

export default function StepReview() {
  const {
    isEditMode,
    deploymentType,
    deploymentName,
    selectedLlm,
    connections,
    selectedVersionByFlow,
    toolNameByFlow,
    setToolNameByFlow,
    attachedConnectionByFlow,
    removedFlowIds,
    setHasToolNameErrors,
  } = useDeploymentStepper();

  const { t } = useTranslation();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFolderId = folderId ?? myCollectionId;

  const { data: flowsData } = useGetRefreshFlowsQuery(
    {
      get_all: true,
      remove_example_flows: true,
    },
    { enabled: !!currentFolderId },
  );
  const allFlows = useMemo(
    () =>
      (Array.isArray(flowsData) ? flowsData : []).filter(
        (flow) => flow.folder_id === currentFolderId,
      ),
    [currentFolderId, flowsData],
  );

  const reviewFlows = useMemo(
    () =>
      buildReviewFlows({
        allFlows,
        attachedConnectionByFlow,
        connections,
        removedFlowIds,
        selectedVersionByFlow,
        toolNameByFlow,
      }),
    [
      allFlows,
      attachedConnectionByFlow,
      connections,
      removedFlowIds,
      selectedVersionByFlow,
      toolNameByFlow,
    ],
  );
  const removedReviewFlows = useMemo(
    () =>
      Array.from(selectedVersionByFlow.entries())
        .filter(([attachmentKey, entry]) =>
          removedFlowIds.has(entry.key ?? attachmentKey),
        )
        .map(([attachmentKey, entry]) => {
          const normalizedAttachmentKey = entry.key ?? attachmentKey;
          const flowName =
            allFlows.find((flow) => flow.id === entry.flowId)?.name ??
            entry.flowName ??
            UNKNOWN_FLOW_NAME;
          return {
            attachmentKey: normalizedAttachmentKey,
            flowName,
            versionLabel: entry.versionTag || entry.versionId,
          };
        }),
    [allFlows, removedFlowIds, selectedVersionByFlow],
  );

  useEffect(() => {
    setHasToolNameErrors(false);
  }, [setHasToolNameErrors]);

  useEffect(() => {
    return () => setHasToolNameErrors(false);
  }, [setHasToolNameErrors]);

  return (
    <div className="flex flex-col gap-4 py-3">
      <div>
        <h2 className="text-lg font-semibold">
          {t("deployments.reviewAndConfirm")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("deployments.reviewDetails")}
        </p>
      </div>

      <ReviewSummaryCard
        deploymentName={deploymentName}
        deploymentType={deploymentType}
        reviewFlows={reviewFlows}
        selectedLlm={selectedLlm}
      />

      {reviewFlows.length > 0 && (
        <div className="flex flex-col gap-3">
          {reviewFlows.map((item) => {
            return (
              <ReviewFlowConfigCard
                key={item.attachmentKey}
                item={item}
                toolNameValue={
                  toolNameByFlow.get(item.attachmentKey)?.trim() ?? ""
                }
                onSaveToolName={(name) => {
                  setToolNameByFlow((prev) => {
                    const next = new Map(prev);
                    if (name.trim()) {
                      next.set(item.attachmentKey, name.trim());
                    } else {
                      next.delete(item.attachmentKey);
                    }
                    return next;
                  });
                }}
              />
            );
          })}
        </div>
      )}

      {isEditMode && (
        <ReviewDetachingSection removedFlows={removedReviewFlows} />
      )}
    </div>
  );
}
