import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import { cn } from "@/utils/utils";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";
import ModelSelection from "./ModelSelection";
import ProviderConfigurationForm from "./ProviderConfigurationForm";

interface ModelProvidersContentProps {
  modelType: "llm" | "embeddings" | "all";
  onFlushRef?: React.MutableRefObject<(() => Promise<void>) | null>;
  onHasChangesRef?: React.MutableRefObject<(() => boolean) | null>;
}

const ModelProvidersContent = ({
  modelType,
  onFlushRef,
  onHasChangesRef,
}: ModelProvidersContentProps) => {
  const { t } = useTranslation();
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  const [providerQuery, setProviderQuery] = useState<string>("");

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
    flushPendingChanges,
    hasUserMadeChanges,
    requiresConfiguration,
  } = useProviderConfiguration({
    selectedProvider,
  });

  // Expose flushPendingChanges and hasUserMadeChanges to the parent
  // (ModelProviderModal) via refs so it can decide whether to refresh model
  // inputs on close.
  useEffect(() => {
    if (onFlushRef) {
      onFlushRef.current = flushPendingChanges;
    }
    if (onHasChangesRef) {
      onHasChangesRef.current = hasUserMadeChanges;
    }
    return () => {
      if (onFlushRef) {
        onFlushRef.current = null;
      }
      if (onHasChangesRef) {
        onHasChangesRef.current = null;
      }
    };
  }, [onFlushRef, onHasChangesRef, flushPendingChanges, hasUserMadeChanges]);

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
  };

  return (
    <div className="flex flex-row w-full h-full overflow-hidden">
      <div
        className={cn(
          "flex p-2 flex-col flex-shrink-0 transition-all duration-300 ease-in-out",
          syncedSelectedProvider ? "w-1/3 border-r" : "w-full",
        )}
      >
        <Input
          icon="Search"
          value={providerQuery}
          onChange={(event) => setProviderQuery(event.target.value)}
          placeholder={t("modelProviders.searchProviders", {
            defaultValue: "Search providers…",
          })}
          aria-label={t("modelProviders.searchProviders", {
            defaultValue: "Search providers…",
          })}
          data-testid="provider-search-input"
          className="mb-2"
        />
        <ProviderList
          modelType={modelType}
          onProviderSelect={handleProviderSelect}
          selectedProviderName={syncedSelectedProvider?.provider ?? null}
          query={providerQuery}
        />
      </div>

      <div
        className={cn(
          "flex min-h-0 flex-col gap-1 transition-all duration-300 ease-in-out",
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

        <div className="relative flex min-h-0 flex-1 flex-col">
          <div className="flex h-full flex-col gap-3 overflow-y-auto px-4 pt-4 pb-6 transition-all duration-300 ease-in-out">
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
          <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-background via-background/70 to-transparent" />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-background via-background/70 to-transparent" />
        </div>
      </div>
    </div>
  );
};

export default ModelProvidersContent;
