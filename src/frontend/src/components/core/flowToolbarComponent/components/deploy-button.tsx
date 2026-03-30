import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version/use-post-create-snapshot";
import { ENABLE_DEPLOYMENTS } from "@/customization/feature-flags";
import DeploymentStepperModal from "@/pages/MainPage/pages/deploymentsPage/components/deployment-stepper-modal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useSaveFlow from "../../../../hooks/flows/use-save-flow";

function DeployButtonInner() {
  const [isPreparingDeploy, setIsPreparingDeploy] = useState(false);
  const [deployModalOpen, setDeployModalOpen] = useState(false);
  const [initialVersionByFlow, setInitialVersionByFlow] = useState<
    Map<string, { versionId: string; versionTag: string }>
  >(new Map());

  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const saveFlow = useSaveFlow();
  const { mutateAsync: createSnapshot } = usePostCreateSnapshot();
  const setErrorData = useAlertStore((state) => state.setErrorData);

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
      setDeployModalOpen(true);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      setErrorData({ title: "Failed to prepare deployment", list: [message] });
    } finally {
      setIsPreparingDeploy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={handleDeploy}
        disabled={isPreparingDeploy || !currentFlowId}
        className="relative inline-flex h-8 items-center justify-start gap-1.5 rounded bg-primary px-2 text-sm font-normal text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        data-testid="deploy-btn-flow"
      >
        <ForwardedIconComponent
          name="Rocket"
          className={`h-4 w-4 ${isPreparingDeploy ? "animate-pulse" : ""}`}
        />
        <span className="font-normal text-mmd">Deploy</span>
      </button>
      <DeploymentStepperModal
        open={deployModalOpen}
        setOpen={setDeployModalOpen}
        initialFlowId={currentFlowId}
        initialVersionByFlow={initialVersionByFlow}
      />
    </>
  );
}

export default function DeployButton() {
  if (!ENABLE_DEPLOYMENTS) return null;
  return <DeployButtonInner />;
}
