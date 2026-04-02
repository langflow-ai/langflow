import { useEffect, useState } from "react";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import type { CustomProviderRead } from "@/types/custom-providers";
import { cn } from "@/utils/utils";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";
import CustomProviderForm from "./CustomProviderForm";
import CustomProviderSection from "./CustomProviderSection";
import ModelSelection from "./ModelSelection";
import ProviderConfigurationForm from "./ProviderConfigurationForm";

interface ModelProvidersContentProps {
  modelType: "llm" | "embeddings" | "all";
  onFlushRef?: React.MutableRefObject<(() => Promise<void>) | null>;
}

/**
 * Tracks which kind of provider is selected in the left panel:
 * - "builtin" — one of the standard providers (OpenAI, Anthropic, etc.)
 * - "custom" — an existing custom provider (has an id)
 * - "new-custom" — the "Add Custom Provider" ghost card
 * - null — nothing selected
 */
type SelectionMode = "builtin" | "custom" | "new-custom" | null;

const ModelProvidersContent = ({
  modelType,
  onFlushRef,
}: ModelProvidersContentProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );

  // Custom provider selection state
  const [selectionMode, setSelectionMode] = useState<SelectionMode>(null);
  const [selectedCustomProvider, setSelectedCustomProvider] =
    useState<CustomProviderRead | null>(null);

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
    requiresConfiguration,
  } = useProviderConfiguration({
    selectedProvider,
  });

  // Expose flushPendingChanges to the parent (ModelProviderModal) via ref
  useEffect(() => {
    if (onFlushRef) {
      onFlushRef.current = flushPendingChanges;
    }
    return () => {
      if (onFlushRef) {
        onFlushRef.current = null;
      }
    };
  }, [onFlushRef, flushPendingChanges]);

  const handleProviderSelect = (provider: Provider) => {
    // Clear custom provider selection
    setSelectedCustomProvider(null);

    if (
      selectionMode === "builtin" &&
      selectedProvider?.provider === provider.provider
    ) {
      // Deselect
      setSelectedProvider(null);
      setSelectionMode(null);
    } else {
      setSelectedProvider(provider);
      setSelectionMode("builtin");
    }
  };

  const handleCustomProviderSelect = (
    providerOrNew: CustomProviderRead | "new",
  ) => {
    // Clear built-in provider selection
    setSelectedProvider(null);

    if (providerOrNew === "new") {
      if (selectionMode === "new-custom") {
        // Deselect
        setSelectionMode(null);
        setSelectedCustomProvider(null);
      } else {
        setSelectionMode("new-custom");
        setSelectedCustomProvider(null);
      }
    } else {
      if (
        selectionMode === "custom" &&
        selectedCustomProvider?.id === providerOrNew.id
      ) {
        // Deselect
        setSelectionMode(null);
        setSelectedCustomProvider(null);
      } else {
        setSelectionMode("custom");
        setSelectedCustomProvider(providerOrNew);
      }
    }
  };

  const handleCustomProviderDone = () => {
    setSelectionMode(null);
    setSelectedCustomProvider(null);
  };

  const isRightPanelOpen =
    (selectionMode === "builtin" && syncedSelectedProvider !== null) ||
    selectionMode === "custom" ||
    selectionMode === "new-custom";

  return (
    <div className="flex flex-row w-full h-full overflow-hidden">
      <div
        className={cn(
          "flex p-2 flex-col flex-shrink-0 transition-all duration-300 ease-in-out overflow-y-auto",
          isRightPanelOpen ? "w-1/3 border-r" : "w-full",
        )}
      >
        <ProviderList
          modelType={modelType}
          onProviderSelect={handleProviderSelect}
          selectedProviderName={
            selectionMode === "builtin"
              ? (syncedSelectedProvider?.provider ?? null)
              : null
          }
        />
        <CustomProviderSection
          selectedCustomProviderId={
            selectionMode === "custom"
              ? (selectedCustomProvider?.id ?? null)
              : selectionMode === "new-custom"
                ? "new"
                : null
          }
          onSelect={handleCustomProviderSelect}
        />
      </div>

      <div
        className={cn(
          "flex min-h-0 flex-col gap-1 transition-all duration-300 ease-in-out",
          isRightPanelOpen
            ? "w-2/3 opacity-100 translate-x-0"
            : "w-0 opacity-0 translate-x-full",
        )}
      >
        {selectionMode === "builtin" && syncedSelectedProvider && (
          <>
            <ProviderConfigurationForm
              key={syncedSelectedProvider.provider}
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
                  availableModels={syncedSelectedProvider.models || []}
                  onModelToggle={handleModelToggle}
                  providerName={syncedSelectedProvider.provider}
                  isEnabledModel={
                    !!(
                      syncedSelectedProvider.is_enabled ||
                      syncedSelectedProvider.is_configured
                    )
                  }
                />
              </div>
              <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-background via-background/70 to-transparent" />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-background via-background/70 to-transparent" />
            </div>
          </>
        )}

        {(selectionMode === "custom" || selectionMode === "new-custom") && (
          <CustomProviderForm
            key={selectedCustomProvider?.id ?? "new"}
            provider={selectedCustomProvider}
            onDone={handleCustomProviderDone}
          />
        )}
      </div>
    </div>
  );
};

export default ModelProvidersContent;
