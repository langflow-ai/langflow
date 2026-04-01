import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetFlowDeploymentAttachments } from "@/controllers/API/queries/deployments";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version/use-post-create-snapshot";
import { ENABLE_DEPLOYMENTS } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import DeploymentStepperModal from "@/pages/MainPage/pages/deploymentsPage/components/deployment-stepper-modal";
import type { FlowDeploymentAttachment } from "@/pages/MainPage/pages/deploymentsPage/types";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useSaveFlow from "../../../../hooks/flows/use-save-flow";
import DeployChoiceDialog from "./deploy-choice-dialog";

function DeployButtonInner() {
  const [isPreparingDeploy, setIsPreparingDeploy] = useState(false);
  const [deployModalOpen, setDeployModalOpen] = useState(false);
  const [choiceDialogOpen, setChoiceDialogOpen] = useState(false);
  const [existingAttachments, setExistingAttachments] = useState<
    FlowDeploymentAttachment[]
  >([]);
  const [pendingSnapshotVersionId, setPendingSnapshotVersionId] = useState("");
  const [initialVersionByFlow, setInitialVersionByFlow] = useState<
    Map<string, { versionId: string; versionTag: string }>
  >(new Map());

  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const saveFlow = useSaveFlow();
  const { mutateAsync: createSnapshot } = usePostCreateSnapshot();
  const { refetch: fetchAttachments } = useGetFlowDeploymentAttachments(
    { flowId: currentFlowId ?? "" },
    { enabled: false },
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const navigate = useCustomNavigate();

  const handleDeploy = async () => {
    if (!currentFlowId) return;
    setIsPreparingDeploy(true);
    try {
      await saveFlow();
      const snapshot = await createSnapshot({ flowId: currentFlowId });
      const versionMap = new Map<
        string,
        { versionId: string; versionTag: string }
      >();
      versionMap.set(currentFlowId, {
        versionId: snapshot.id,
        versionTag: snapshot.version_tag,
      });
      setInitialVersionByFlow(versionMap);

      // Check for existing deployments
      const { data } = await fetchAttachments();

      if (data && data.attachments.length > 0) {
        setExistingAttachments(data.attachments);
        setPendingSnapshotVersionId(snapshot.id);
        setChoiceDialogOpen(true);
      } else {
        setDeployModalOpen(true);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      setErrorData({ title: "Failed to prepare deployment", list: [message] });
    } finally {
      setIsPreparingDeploy(false);
    }
  };

  const handleChooseNew = () => {
    setChoiceDialogOpen(false);
    setDeployModalOpen(true);
  };

  const handleUpdateComplete = (deploymentName: string) => {
    setChoiceDialogOpen(false);
    setExistingAttachments([]);
    setPendingSnapshotVersionId("");
    setSuccessData({
      title: `Deployment "${deploymentName}" updated successfully`,
    });
  };

  return (
    <>
      <button
        type="button"
        onClick={handleDeploy}
        disabled={
          isPreparingDeploy ||
          choiceDialogOpen ||
          deployModalOpen ||
          !currentFlowId
        }
        className="relative inline-flex h-8 items-center justify-start gap-1.5 rounded bg-primary px-2 text-sm font-normal text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        data-testid="deploy-btn-flow"
      >
        <ForwardedIconComponent
          name="Rocket"
          className={`h-4 w-4 ${isPreparingDeploy ? "animate-pulse" : ""}`}
        />
        <span className="font-normal text-mmd">Deploy</span>
      </button>
      <DeployChoiceDialog
        open={choiceDialogOpen}
        setOpen={setChoiceDialogOpen}
        attachments={existingAttachments}
        snapshotVersionId={pendingSnapshotVersionId}
        onChooseNew={handleChooseNew}
        onUpdateComplete={handleUpdateComplete}
      />
      <DeploymentStepperModal
        open={deployModalOpen}
        setOpen={setDeployModalOpen}
        initialFlowId={currentFlowId}
        initialVersionByFlow={initialVersionByFlow}
        onTestDeployment={(deployment, providerId) => {
          setDeployModalOpen(false);
          navigate("/all", {
            state: {
              flowType: "deployments",
              testDeployment: deployment,
              testProviderId: providerId,
            },
          });
        }}
      />
    </>
  );
}

export default function DeployButton() {
  if (!ENABLE_DEPLOYMENTS) return null;
  return <DeployButtonInner />;
}
