import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import CustomModelProvidersEmptyState from "@/customization/components/custom-model-providers-empty-state";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import type { ModelTypeFilter } from "@/types/models";
import { cn } from "@/utils/utils";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";
import ModelSelection, { hasProviderOwnedEmptyState } from "./ModelSelection";
import ProviderConfigurationForm from "./ProviderConfigurationForm";

interface ModelProvidersContentProps extends ProviderScopeParams {
  modelType: ModelTypeFilter;
  onFlushRef?: React.MutableRefObject<(() => Promise<void>) | null>;
  onHasChangesRef?: React.MutableRefObject<(() => boolean) | null>;
}

const ModelProvidersContent = ({
  modelType,
  onFlushRef,
  onHasChangesRef,
  flowId,
  projectId,
}: ModelProvidersContentProps) => {
  const { t } = useTranslation();
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  const [providerQuery, setProviderQuery] = useState<string>("");
  const providerContentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (providerContentRef.current) {
      providerContentRef.current.scrollTop = 0;
    }
  }, [selectedProvider?.provider]);

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
    flowId,
    projectId,
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

  const typedModelCount = (syncedSelectedProvider?.models ?? []).filter(
    (model) => modelType === "all" || model.metadata?.model_type === modelType,
  ).length;
  // Providers whose catalog is discovered from their endpoint have no models
  // to show until credentials are configured; ModelSelection renders a
  // configure-credentials hint for them instead of the generic empty state.
  const awaitingLiveDiscovery =
    !!syncedSelectedProvider?.live_discovery &&
    !syncedSelectedProvider?.is_configured;
  const showNoAvailableModels =
    !!syncedSelectedProvider &&
    typedModelCount === 0 &&
    !awaitingLiveDiscovery &&
    !hasProviderOwnedEmptyState(syncedSelectedProvider.provider);

  return (
    <div className="flex flex-row w-full h-full overflow-hidden">
      <div
        className={cn(
          "flex min-h-0 p-2 flex-col flex-shrink-0 transition-all duration-300 ease-in-out",
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
        <div
          className="min-h-0 flex-1 overflow-y-auto"
          data-testid="provider-list-scroll"
        >
          <ProviderList
            modelType={modelType}
            onProviderSelect={handleProviderSelect}
            selectedProviderName={syncedSelectedProvider?.provider ?? null}
            query={providerQuery}
            flowId={flowId}
            projectId={projectId}
          />
        </div>
      </div>

      <div
        ref={providerContentRef}
        data-testid="provider-content-scroll"
        className={cn(
          "min-h-0 overflow-y-auto transition-all duration-300 ease-in-out",
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

        {/* Hidden without a selection because the padded content has intrinsic
            width, so it would stick out of the w-0 column and register as
            clipped content at a 320px viewport (WCAG 1.4.10). */}
        <div
          className={cn("px-4 pt-4 pb-6", !syncedSelectedProvider && "hidden")}
        >
          <CustomModelProvidersEmptyState
            kind="models"
            show={showNoAvailableModels}
          >
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
              liveDiscovery={!!syncedSelectedProvider?.live_discovery}
              isConfigured={!!syncedSelectedProvider?.is_configured}
              flowId={flowId}
              projectId={projectId}
            />
          </CustomModelProvidersEmptyState>
        </div>
      </div>
    </div>
  );
};

export default ModelProvidersContent;
