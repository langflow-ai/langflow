import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type AvailableDBProviderId,
  DB_PROVIDER_OPTIONS,
  type DBProviderId,
  getActiveDBProvider,
  getDBProviderConfig,
  getGlobalVariableValue,
  isDBProviderConfigured,
  OPENSEARCH_VARIABLES,
} from "@/constants/dbProviderConstants";
import SettingsPageHeader from "@/pages/SettingsPage/components/SettingsPageHeader";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { ProviderConfigurationPanel } from "./components/ProviderConfigurationPanel";
import { ProviderListItem } from "./components/ProviderListItem";
import { useDBProviderActions } from "./hooks/useDBProviderActions";
import { useDBProviderFields } from "./hooks/useDBProviderFields";
import { useDBProviderVariables } from "./hooks/useDBProviderVariables";

export default function DBProvidersPage() {
  const { t } = useTranslation();
  const { globalVariables, isPending, setVariable, activateProvider } =
    useDBProviderVariables();
  const localVectorStoreAvailable = useUtilityStore(
    (state) => state.localVectorStoreAvailable,
  );
  const defaultVectorStoreBackend = useUtilityStore(
    (state) => state.defaultVectorStoreBackend,
  );
  const configuredVectorStoreBackends = useUtilityStore(
    (state) => state.configuredVectorStoreBackends,
  );
  // Local SQLite writes to the serving box's disk, which the production profile
  // refuses. Hide it here too — this page sets the global default, so leaving it
  // selectable would let an operator re-enable the exact backend the create
  // endpoint rejects.
  const visibleProviders = useMemo(
    () =>
      DB_PROVIDER_OPTIONS.filter(
        (provider) => localVectorStoreAvailable || provider.id !== "sqlite",
      ),
    [localVectorStoreAvailable],
  );
  const [selectedProviderId, setSelectedProviderId] = useState<DBProviderId>(
    getActiveDBProvider(
      globalVariables,
      localVectorStoreAvailable,
      defaultVectorStoreBackend,
      configuredVectorStoreBackends,
    ),
  );
  const [hasManuallySelectedProvider, setHasManuallySelectedProvider] =
    useState(false);
  const [variableValues, setVariableValues] = useState<Record<string, string>>(
    {},
  );
  const [editingSecret, setEditingSecret] = useState<Record<string, boolean>>(
    {},
  );

  const activeProviderId = useMemo(
    () =>
      getActiveDBProvider(
        globalVariables,
        localVectorStoreAvailable,
        defaultVectorStoreBackend,
        configuredVectorStoreBackends,
      ),
    [
      globalVariables,
      localVectorStoreAvailable,
      defaultVectorStoreBackend,
      configuredVectorStoreBackends,
    ],
  );

  useEffect(() => {
    if (!hasManuallySelectedProvider) {
      setSelectedProviderId(activeProviderId);
    }
  }, [activeProviderId, hasManuallySelectedProvider]);

  const selectedProvider =
    visibleProviders.find((provider) => provider.id === selectedProviderId) ??
    visibleProviders[0];

  const hasServerConfiguration =
    selectedProvider.id === "opensearch" &&
    (configuredVectorStoreBackends.includes("opensearch") ||
      defaultVectorStoreBackend === "opensearch") &&
    !getGlobalVariableValue(globalVariables, OPENSEARCH_VARIABLES.URL);
  const useServerConfiguration =
    hasServerConfiguration &&
    !selectedProvider.configFields.some(
      (field) => field.variableKey in variableValues,
    );

  const { getFieldValue, isHydrated, canSave } = useDBProviderFields({
    selectedProvider,
    globalVariables,
    variableValues,
  });

  const {
    handleSave,
    handleTestConnection,
    handleUseSQLite,
    handleUsePostgres,
    isTesting,
    postgresStatus,
    isCheckingPostgres,
  } = useDBProviderActions({
    selectedProvider,
    canSave: canSave || useServerConfiguration,
    serverBackendConfig: useServerConfiguration
      ? getDBProviderConfig("opensearch", globalVariables)
      : undefined,
    getFieldValue,
    variableValues,
    setVariable,
    activateProvider,
    setVariableValues,
    setEditingSecret,
    setHasManuallySelectedProvider,
    setSelectedProviderId,
  });

  return (
    <div className="flex w-full flex-col gap-6">
      <SettingsPageHeader
        title={t("settings.dbProviders.title")}
        description={t("settings.dbProviders.description")}
      />

      <div className="flex h-[calc(100vh-305px)] w-full overflow-hidden rounded-lg border">
        <div
          className={cn(
            "flex flex-col gap-1 p-2 transition-all duration-300 ease-in-out",
            selectedProvider ? "w-1/3 border-r" : "w-full",
          )}
        >
          {visibleProviders.map((provider) => (
            <ProviderListItem
              key={provider.id}
              provider={provider}
              isActive={activeProviderId === provider.id}
              isSelected={selectedProvider.id === provider.id}
              isConfigured={
                provider.status === "available" &&
                isDBProviderConfigured(
                  provider.id as AvailableDBProviderId,
                  globalVariables,
                  localVectorStoreAvailable,
                  defaultVectorStoreBackend,
                  configuredVectorStoreBackends,
                )
              }
              onSelect={() => {
                setHasManuallySelectedProvider(true);
                setSelectedProviderId(provider.id);
              }}
            />
          ))}
        </div>

        <div className="flex min-h-0 w-2/3 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4">
            <ProviderConfigurationPanel
              provider={selectedProvider}
              activeProviderId={activeProviderId}
              globalVariables={globalVariables}
              variableValues={variableValues}
              editingSecret={editingSecret}
              isPending={isPending}
              canSave={canSave || useServerConfiguration}
              isHydrated={isHydrated || useServerConfiguration}
              hasServerConfiguration={hasServerConfiguration}
              getFieldValue={getFieldValue}
              onVariableChange={(key, value) =>
                setVariableValues((prev) => ({ ...prev, [key]: value }))
              }
              onSecretEditingChange={(key, editing) =>
                setEditingSecret((prev) => ({ ...prev, [key]: editing }))
              }
              onSave={
                selectedProvider.id === "sqlite"
                  ? handleUseSQLite
                  : selectedProvider.id === "postgres"
                    ? handleUsePostgres
                    : () => {
                        void handleSave();
                      }
              }
              onTestConnection={
                selectedProvider.id === "sqlite"
                  ? undefined
                  : handleTestConnection
              }
              isTesting={isTesting}
              postgresStatus={postgresStatus}
              isCheckingPostgres={isCheckingPostgres}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
