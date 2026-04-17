import { useCallback, useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { useToolNameValidation } from "../hooks/use-tool-name-validation";
import { StepReviewDetachingSection } from "./step-review-detaching-section";
import { StepReviewFlowConfigCard } from "./step-review-flow-config-card";
import { StepReviewSummaryCard } from "./step-review-summary-card";
import type {
  RemovedReviewFlowItem,
  ReviewFlowItem,
} from "./step-review-types";

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
    selectedInstance,
    preExistingFlowIds,
    initialToolNameByFlow,
    setHasToolNameErrors,
  } = useDeploymentStepper();

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
    [flowsData, currentFolderId],
  );

  const flowsById = useMemo(
    () => new Map(allFlows.map((flow) => [flow.id, flow])),
    [allFlows],
  );

  const connectionsById = useMemo(
    () => new Map(connections.map((connection) => [connection.id, connection])),
    [connections],
  );

  const reviewFlows = useMemo<ReviewFlowItem[]>(
    () =>
      Array.from(selectedVersionByFlow.entries()).map(
        ([flowId, { versionId, versionTag }]) => {
          const flow = flowsById.get(flowId);
          const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
          const connectionDetails = connectionIds
            .map((connectionId) => connectionsById.get(connectionId))
            .filter(
              (connection): connection is NonNullable<typeof connection> =>
                connection != null,
            )
            .map((connection) => ({
              name: connection.name,
              isNew: connection.isNew ?? false,
              envVars: Object.keys(connection.environmentVariables ?? {}).map(
                (key) => ({
                  key,
                  masked: "••••••••",
                }),
              ),
            }));

          const flowName = flow?.name ?? "Unknown";

          return {
            flowId,
            flowName,
            toolName: toolNameByFlow.get(flowId)?.trim() || flowName,
            versionLabel: versionTag || versionId,
            connectionDetails,
          };
        },
      ),
    [
      selectedVersionByFlow,
      flowsById,
      attachedConnectionByFlow,
      connectionsById,
      toolNameByFlow,
    ],
  );

  const removedFlows = useMemo<RemovedReviewFlowItem[]>(
    () =>
      Array.from(removedFlowIds).map((flowId) => ({
        flowId,
        flowName: flowsById.get(flowId)?.name ?? "Unknown flow",
      })),
    [removedFlowIds, flowsById],
  );

  const { toolNameErrors } = useToolNameValidation({
    reviewFlows,
    selectedInstanceId: selectedInstance?.id,
    isEditMode,
    preExistingFlowIds,
    initialToolNameByFlow,
  });

  useEffect(() => {
    setHasToolNameErrors(toolNameErrors.size > 0);
  }, [toolNameErrors, setHasToolNameErrors]);

  useEffect(() => {
    return () => setHasToolNameErrors(false);
  }, [setHasToolNameErrors]);

  const handleSaveToolName = useCallback(
    (flowId: string, name: string) => {
      setToolNameByFlow((prev) => {
        const next = new Map(prev);
        if (name.trim()) {
          next.set(flowId, name.trim());
        } else {
          next.delete(flowId);
        }
        return next;
      });
    },
    [setToolNameByFlow],
  );

  return (
    <div className="flex flex-col gap-4 py-3">
      <div>
        <h2 className="text-lg font-semibold">Review & Confirm</h2>
        <p className="text-sm text-muted-foreground">
          Review your deployment details before creating.
        </p>
      </div>

      <StepReviewSummaryCard
        deploymentType={deploymentType}
        deploymentName={deploymentName}
        selectedLlm={selectedLlm}
        reviewFlows={reviewFlows}
      />

      {reviewFlows.length > 0 && (
        <div className="flex flex-col gap-3">
          {reviewFlows.map((item) => (
            <StepReviewFlowConfigCard
              key={item.flowId}
              item={item}
              toolError={toolNameErrors.get(item.flowId)}
              toolNameValue={toolNameByFlow.get(item.flowId)?.trim() ?? ""}
              onSaveToolName={handleSaveToolName}
            />
          ))}
        </div>
      )}

      {isEditMode && <StepReviewDetachingSection removedFlows={removedFlows} />}
    </div>
  );
}
