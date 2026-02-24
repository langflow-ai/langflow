import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { StepperModal, StepperModalFooter } from "@/modals/stepperModal";
import { columnDefs } from "./columnDefs";
import { TOGGLE_OPTIONS, TOTAL_STEPS } from "./constants";
import { DeploymentProvidersView } from "./DeploymentProvidersView";
import { MOCK_DEPLOYMENTS } from "./mockData";
import { StepAttach } from "./steps/StepAttach";
import { StepBasics } from "./steps/StepBasics";
import { StepConfiguration } from "./steps/StepConfiguration";
import { StepReview } from "./steps/StepReview";
import { StepScope } from "./steps/StepScope";
import { useDeploymentForm } from "./useDeploymentForm";

const DeploymentsTab = () => {
  const {
    activeView,
    setActiveView,
    newDeploymentOpen,
    currentStep,
    deploymentType,
    setDeploymentType,
    deploymentName,
    setDeploymentName,
    deploymentDescription,
    setDeploymentDescription,
    selectedItems,
    attachTab,
    setAttachTab,
    configMode,
    setConfigMode,
    configName,
    setConfigName,
    keyFormat,
    setKeyFormat,
    envVars,
    setEnvVars,
    variableScope,
    setVariableScope,
    handleBack,
    handleNext,
    handleSubmit,
    handleOpenChange,
    toggleItem,
  } = useDeploymentForm();

  return (
    <div className="flex h-full flex-col p-5">
      <div className="flex justify-between items-center">
        <div className="relative flex h-9 items-center rounded-lg border border-border bg-background p-1">
          <div
            className="absolute h-7 rounded-md bg-muted shadow-sm transition-all duration-200"
            style={{
              width: activeView === "Live Deployments" ? 133 : 175,
              left: activeView === "Live Deployments" ? "4px" : 141,
            }}
          />
          {TOGGLE_OPTIONS.map((option) => (
            <button
              key={option}
              onClick={() => setActiveView(option)}
              className={`relative z-10 flex-1 whitespace-nowrap rounded-md px-3 py-1 text-center text-sm font-medium transition-colors ${
                activeView === option
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={() => {
            if (activeView === "Deployment Providers") {
              // TODO: Open provider modal
              alert("Open provider modal");
            } else {
              handleOpenChange(true);
            }
          }}
        >
          <ForwardedIconComponent name="Plus" />{" "}
          {activeView === "Deployment Providers"
            ? "Add Provider"
            : "New Deployment"}
        </Button>
      </div>

      {activeView === "Deployment Providers" && (
        <div className="pt-4">
          <DeploymentProvidersView />
        </div>
      )}

      {activeView === "Live Deployments" && (
        <div className="flex h-full flex-col pt-4">
          <div className="relative h-full">
            <TableComponent
              rowHeight={65}
              cellSelection={false}
              tableOptions={{ hide_options: true }}
              columnDefs={columnDefs}
              rowData={MOCK_DEPLOYMENTS}
              className="w-full ag-no-border"
              pagination
              quickFilterText=""
              gridOptions={{
                ensureDomOrder: true,
                colResizeDefault: "shift",
              }}
            />
          </div>
        </div>
      )}
      <StepperModal
        open={newDeploymentOpen}
        onOpenChange={handleOpenChange}
        currentStep={currentStep}
        totalSteps={TOTAL_STEPS}
        title="Create Deployment"
        contentClassName="bg-secondary"
        icon="Rocket"
        description="Deploy your Langflow workflows to watsonx Orchestrate"
        showProgress
        width="w-[800px]"
        height="h-[700px]"
        size="medium-h-full"
        footer={
          <StepperModalFooter
            currentStep={currentStep}
            totalSteps={TOTAL_STEPS}
            onBack={handleBack}
            onNext={handleNext}
            onSubmit={handleSubmit}
            nextDisabled={
              (currentStep === 1 && !deploymentName.trim()) ||
              (currentStep === 2 && selectedItems.size === 0) ||
              (currentStep === 3 && !configName.trim())
            }
            submitLabel="Deployment"
          />
        }
      >
        {currentStep === 1 && (
          <StepBasics
            deploymentName={deploymentName}
            setDeploymentName={setDeploymentName}
            deploymentDescription={deploymentDescription}
            setDeploymentDescription={setDeploymentDescription}
            deploymentType={deploymentType}
            setDeploymentType={setDeploymentType}
          />
        )}

        {currentStep === 2 && (
          <StepAttach
            attachTab={attachTab}
            setAttachTab={setAttachTab}
            selectedItems={selectedItems}
            toggleItem={toggleItem}
          />
        )}

        {currentStep === 3 && (
          <StepConfiguration
            configMode={configMode}
            setConfigMode={setConfigMode}
            configName={configName}
            setConfigName={setConfigName}
            keyFormat={keyFormat}
            setKeyFormat={setKeyFormat}
            envVars={envVars}
            setEnvVars={setEnvVars}
          />
        )}
        {currentStep === 4 && (
          <StepScope
            variableScope={variableScope}
            setVariableScope={setVariableScope}
          />
        )}
        {currentStep === 5 && (
          <StepReview
            deploymentType={deploymentType}
            deploymentName={deploymentName}
            deploymentDescription={deploymentDescription}
            selectedItems={selectedItems}
            configMode={configMode}
            configName={configName}
            keyFormat={keyFormat}
            envVars={envVars}
            variableScope={variableScope}
          />
        )}
      </StepperModal>
    </div>
  );
};

export default DeploymentsTab;
