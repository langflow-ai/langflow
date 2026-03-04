import { useState } from "react";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import { cn } from "@/utils/utils";
import ModelSelection from "./ModelSelection";
import ProviderConfigurationForm from "./ProviderConfigurationForm";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";

interface ModelProvidersContentProps {
  modelType: "llm" | "embeddings" | "all";
}

const ModelProvidersContent = ({ modelType }: ModelProvidersContentProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );

  // Use the custom hook for provider configuration logic
  const {
    variableValues,
    validationFailed,
    isSaving,
    isPending,
    isDeleting,
    isFetchingAfterSave,
    isFetchingAfterDisconnect,
    handleVariableChange,
    handleSaveAllVariables,
    handleActivateProvider,
    handleDisconnect,
    isVariableConfigured,
    getConfiguredValue,
    validationState,
    validationError,
    canSave,
    providerVariables,
    syncedSelectedProvider,
    handleModelToggle,
    requiresConfiguration,
  } = useProviderConfiguration({
    selectedProvider,
  });

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
  };

  return (
    <div className="flex flex-row w-full h-full overflow-hidden">
      <div
        className={cn(
          "flex p-2 flex-col transition-all duration-300 ease-in-out",
          syncedSelectedProvider ? "w-1/3 border-r" : "w-full",
        )}
      >
        <ProviderList
          modelType={modelType}
          onProviderSelect={handleProviderSelect}
          selectedProviderName={syncedSelectedProvider?.provider ?? null}
        />
      </div>

      <div
        className={cn(
          "flex flex-col gap-1 transition-all duration-300 ease-in-out overflow-y-auto",
          syncedSelectedProvider
            ? "w-2/3 opacity-100 translate-x-0"
            : "w-0 opacity-0 translate-x-full",
        )}
      >
        <ProviderConfigurationForm
          key={syncedSelectedProvider?.provider}
          selectedProvider={syncedSelectedProvider}
          providerVariables={providerVariables}
          variableValues={variableValues}
          isVariableConfigured={isVariableConfigured}
          getConfiguredValue={getConfiguredValue}
          onVariableChange={handleVariableChange}
          onSave={handleSaveAllVariables}
          onActivate={handleActivateProvider}
          onDisconnect={handleDisconnect}
          isSaving={isSaving}
          isPending={isPending}
          isDeleting={isDeleting}
          isFetchingModels={isFetchingAfterSave}
          isFetchingAfterDisconnect={isFetchingAfterDisconnect}
          validationFailed={validationFailed}
          validationState={validationState}
          validationError={validationError}
          canSave={canSave}
          requiresConfiguration={requiresConfiguration}
        />

        <div className="flex flex-col px-4 pb-4 gap-3 transition-all duration-300 ease-in-out">
          <ModelSelection
            modelType={modelType}
            availableModels={syncedSelectedProvider?.models || []}
            onModelToggle={handleModelToggle}
            providerName={syncedSelectedProvider?.provider}
            isEnabledModel={
              !!(
                syncedSelectedProvider?.is_enabled ||
                syncedSelectedProvider?.is_configured
              )
            }
          />
        </div>
      </div>
    </div>
  );
};

export default ModelProvidersContent;
