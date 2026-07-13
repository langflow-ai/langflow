import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DB_PROVIDER_OPTIONS,
  type DBProviderId,
  type DBProviderTextField,
  getActiveDBProvider,
} from "@/constants/dbProviderConstants";
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
  const [selectedProviderId, setSelectedProviderId] = useState<DBProviderId>(
    getActiveDBProvider(globalVariables),
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
    () => getActiveDBProvider(globalVariables),
    [globalVariables],
  );

  useEffect(() => {
    if (!hasManuallySelectedProvider) {
      setSelectedProviderId(activeProviderId);
    }
  }, [activeProviderId, hasManuallySelectedProvider]);

  const selectedProvider =
    DB_PROVIDER_OPTIONS.find(
      (provider) => provider.id === selectedProviderId,
    ) ?? DB_PROVIDER_OPTIONS[0];

  const { getFieldValue, hasConfiguredValue, isHydrated, canSave } =
    useDBProviderFields({ selectedProvider, globalVariables, variableValues });

  const { handleSave, handleTestConnection, handleUseChroma, isTesting } =
    useDBProviderActions({
      selectedProvider,
      canSave,
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
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            {t("settings.dbProviders.title")}
            <ForwardedIconComponent
              name="Database"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("settings.dbProviders.description")}
          </p>
        </div>
      </div>

      <div className="flex h-[calc(100vh-305px)] w-full overflow-hidden rounded-lg border">
        <div
          className={cn(
            "flex flex-col gap-1 p-2 transition-all duration-300 ease-in-out",
            selectedProvider ? "w-1/3 border-r" : "w-full",
          )}
        >
          {DB_PROVIDER_OPTIONS.map((provider) => (
            <ProviderListItem
              key={provider.id}
              provider={provider}
              isActive={activeProviderId === provider.id}
              isSelected={selectedProvider.id === provider.id}
              isConfigured={
                provider.id === "chroma" ||
                provider.configFields
                  .filter(
                    (field): field is DBProviderTextField =>
                      field.kind !== "boolean" && field.required,
                  )
                  .every((field) => hasConfiguredValue(field.variableKey))
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
              canSave={canSave}
              isHydrated={isHydrated}
              getFieldValue={getFieldValue}
              onVariableChange={(key, value) =>
                setVariableValues((prev) => ({ ...prev, [key]: value }))
              }
              onSecretEditingChange={(key, editing) =>
                setEditingSecret((prev) => ({ ...prev, [key]: editing }))
              }
              onSave={
                selectedProvider.id === "chroma"
                  ? handleUseChroma
                  : () => {
                      void handleSave();
                    }
              }
              onTestConnection={
                selectedProvider.id === "chroma"
                  ? undefined
                  : handleTestConnection
              }
              isTesting={isTesting}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
