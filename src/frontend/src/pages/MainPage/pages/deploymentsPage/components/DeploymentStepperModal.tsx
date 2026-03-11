import ForwardedIconComponent from "@/components/common/genericIconComponent";
import StepperModal, {
  StepperModalFooter,
} from "@/modals/stepperModal/StepperModal";
import { StepAgent } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepAgent";
import { StepBasics } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepBasics";
import { StepConfiguration } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepConfiguration";
import { StepProvider } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepProvider";
import { StepReview } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepReview";
import type { Dispatch, SetStateAction } from "react";
import type { DeploymentType, EnvVar } from "../constants";
import { TOTAL_STEPS } from "../constants";
import type { FlowCheckpointGroup } from "../types";
import { DeployFlowStepper } from "./DeployFlowStepper";

const STEP_LABELS = ["Provider", "Basics", "Agent", "Configure Flow", "Review"];

type DeploymentStepperModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentStep: number;
  deploymentType: DeploymentType;
  setDeploymentType: (type: DeploymentType) => void;
  deploymentName: string;
  setDeploymentName: (name: string) => void;
  deploymentDescription: string;
  setDeploymentDescription: (desc: string) => void;
  selectedItems: Set<string>;
  toggleItem: (id: string) => void;
  checkpointGroups: FlowCheckpointGroup[];
  envVars: EnvVar[];
  setEnvVars: Dispatch<SetStateAction<EnvVar[]>>;
  detectedVarCount: number;
  selectedReviewItems: { name: string }[];
  providerName?: string;
  onBack: () => void;
  onNext: () => void;
  onSubmit: () => void;
};

export const DeploymentStepperModal = ({
  open,
  onOpenChange,
  currentStep,
  deploymentType,
  setDeploymentType,
  deploymentName,
  setDeploymentName,
  deploymentDescription,
  setDeploymentDescription,
  selectedItems,
  toggleItem,
  checkpointGroups,
  envVars,
  setEnvVars,
  detectedVarCount,
  selectedReviewItems,
  providerName,
  onBack,
  onNext,
  onSubmit,
}: DeploymentStepperModalProps) => {
  const selectedAgentName = checkpointGroups.find((g) =>
    selectedItems.has(g.flowId),
  )?.flowName;

  return (
    <StepperModal
      className=""
      open={open}
      onOpenChange={onOpenChange}
      currentStep={currentStep}
      totalSteps={TOTAL_STEPS}
      showProgress={false}
      description={
        currentStep === 1
          ? "Configure your provider credentials below. Sign in or sign up to find your credentials"
          : currentStep === 2
            ? "Set your deployment details"
            : currentStep === 3
              ? "Choose an existing agent or create a new one"
              : currentStep === 4
                ? "Assign a configuration to your flow"
                : "Review the details of your deployment before finalizing"
      }
      title={
        currentStep === 1
          ? "Configure Deployment Provider"
          : currentStep === 2
            ? "Deployment Basics"
            : currentStep === 3
              ? "Agent Selection"
              : currentStep === 4
                ? "Configure Flow"
                : "Review & Deploy"
      }
      bgClassName="bg-secondary"
      width="w-[752px]"
      height="h-[569px]"
      contentClassName="bg-background"
      stepLabels={STEP_LABELS}
      onBack={() => onOpenChange(false)}
      backLabel="Back to Deployments"
      footer={
        <StepperModalFooter
          currentStep={currentStep}
          totalSteps={TOTAL_STEPS}
          onBack={onBack}
          onNext={() => {
            onNext();
          }}
          onSubmit={onSubmit}
          submitLabel={
            <>
              <ForwardedIconComponent name="Rocket" className="h-4 w-4" />{" "}
              Deploy
            </>
          }
          nextLabel="Next"
        />
      }
    >
      <DeployFlowStepper currentStep={currentStep} labels={STEP_LABELS} />
      {currentStep === 1 && (
        <StepProvider
          deploymentName={deploymentName}
          setDeploymentName={setDeploymentName}
          deploymentDescription={deploymentDescription}
          setDeploymentDescription={setDeploymentDescription}
          deploymentType={deploymentType}
          setDeploymentType={setDeploymentType}
        />
      )}
      {currentStep === 2 && (
        <StepBasics
          deploymentName={deploymentName}
          setDeploymentName={setDeploymentName}
          deploymentDescription={deploymentDescription}
          setDeploymentDescription={setDeploymentDescription}
          deploymentType={deploymentType}
          setDeploymentType={setDeploymentType}
        />
      )}

      {currentStep === 3 && (
        <StepAgent
          selectedItems={selectedItems}
          toggleItem={toggleItem}
          flows={checkpointGroups}
        />
      )}

      {currentStep === 4 && (
        <StepConfiguration
          envVars={envVars}
          setEnvVars={setEnvVars}
          detectedVarCount={detectedVarCount}
          selectedAgentName={selectedAgentName}
        />
      )}

      {currentStep === 5 && (
        <StepReview
          deploymentType={deploymentType}
          deploymentName={deploymentName}
          deploymentDescription={deploymentDescription}
          selectedItems={selectedReviewItems}
          envVars={envVars}
          providerName={providerName}
          selectedAgentName={selectedAgentName}
        />
      )}
    </StepperModal>
  );
};
