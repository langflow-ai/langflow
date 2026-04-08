import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { ENABLE_DEPLOYMENTS } from "@/customization/feature-flags";
import DeploymentStepperModal from "@/pages/MainPage/pages/deploymentsPage/components/deployment-stepper-modal";
import { useNavigateToTest } from "@/pages/MainPage/pages/deploymentsPage/hooks/use-navigate-to-test";
import DeployChoiceDialog from "./deploy-choice-dialog";
import { usePrepareDeploy } from "./deploy-choice-dialog/hooks/use-prepare-deploy";

function DeployButtonInner() {
  const {
    currentFlowId,
    isPreparingDeploy,
    choiceDialogOpen,
    setChoiceDialogOpen,
    deployModalOpen,
    setDeployModalOpen,
    providers,
    pendingSnapshotVersionId,
    initialVersionByFlow,
    stepperInitialProvider,
    stepperInitialInstance,
    handleDeploy,
    handleChooseNew,
    handleUpdateComplete,
    resetChoiceState,
  } = usePrepareDeploy();

  const navigateToTest = useNavigateToTest();

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
        providers={providers}
        flowId={currentFlowId ?? ""}
        snapshotVersionId={pendingSnapshotVersionId}
        snapshotVersionTag={
          initialVersionByFlow.get(currentFlowId ?? "")?.versionTag ?? ""
        }
        onChooseNew={handleChooseNew}
        onUpdateComplete={handleUpdateComplete}
        onTestDeployment={(deployment, providerId) => {
          resetChoiceState();
          navigateToTest(deployment, providerId);
        }}
      />
      <DeploymentStepperModal
        open={deployModalOpen}
        setOpen={setDeployModalOpen}
        initialFlowId={currentFlowId}
        initialVersionByFlow={initialVersionByFlow}
        initialProvider={stepperInitialProvider}
        initialInstance={stepperInitialInstance}
        onTestDeployment={(deployment, providerId) => {
          setDeployModalOpen(false);
          navigateToTest(deployment, providerId);
        }}
      />
    </>
  );
}

export default function DeployButton() {
  if (!ENABLE_DEPLOYMENTS) return null;
  return <DeployButtonInner />;
}
