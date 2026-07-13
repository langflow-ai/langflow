import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  type AvailableDBProviderId,
  DB_PROVIDER_OPTIONS,
  type DBProviderConfigField,
  type DBProviderId,
  type DBProviderTextField,
  getActiveDBProvider,
  getGlobalVariableValue,
  parseBooleanGlobalVariable,
  toAPIBackendType,
} from "@/constants/dbProviderConstants";
import { useTestDBProviderConnection } from "@/controllers/API/queries/knowledge-bases/use-test-kb-connection";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { ProviderConfigurationPanel } from "./components/ProviderConfigurationPanel";
import { ProviderListItem } from "./components/ProviderListItem";
import { buildBackendConfigPayload } from "./helpers/build-backend-config-payload";
import { useDBProviderVariables } from "./hooks/useDBProviderVariables";

type ApiError = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

const getErrorDetail = (error: unknown) =>
  (error as ApiError)?.response?.data?.detail ||
  "An unexpected error occurred. Please try again.";

export default function DBProvidersPage() {
  const { t } = useTranslation();
  const {
    globalVariables,
    isPending,
    setVariable,
    activateProvider,
  } = useDBProviderVariables();
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

  const { mutateAsync: testProviderConnection, isPending: isTesting } =
    useTestDBProviderConnection();

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

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

  const getFieldValue = (field: DBProviderConfigField): string => {
    if (field.variableKey in variableValues) {
      return variableValues[field.variableKey];
    }
    if (field.kind === "boolean") {
      const stored = parseBooleanGlobalVariable(
        globalVariables,
        field.variableKey,
        field.defaultValue,
      );
      return stored ? "true" : "false";
    }
    return (
      getGlobalVariableValue(globalVariables, field.variableKey) ??
      field.defaultValue ??
      ""
    );
  };

  const hasConfiguredValue = (variableKey: string) =>
    globalVariables.some((variable) => variable.name === variableKey);

  // True when every required field already has a saved variable so the
  // provider can be activated / tested without the user re-entering anything.
  // Secret fields are checked by existence (API responses mask the value);
  // non-secret fields are checked by stored value.
  const isHydrated = selectedProvider.configFields
    .filter(
      (field): field is DBProviderTextField =>
        field.kind !== "boolean" && field.required,
    )
    .every((field) =>
      field.isSecret
        ? hasConfiguredValue(field.variableKey)
        : Boolean(
            getGlobalVariableValue(globalVariables, field.variableKey)?.trim(),
          ),
    );

  // Boolean fields always have a defined value (toggle is never blank),
  // so they don't gate the save button — only required text fields do.
  // Secret fields satisfy the check when the user has typed a new value OR
  // the variable already exists (API response masks saved secrets).
  const canSave = selectedProvider.configFields
    .filter(
      (field): field is DBProviderTextField =>
        field.kind !== "boolean" && field.required,
    )
    .every((field) => {
      if (field.isSecret) {
        return (
          Boolean(variableValues[field.variableKey]?.trim()) ||
          hasConfiguredValue(field.variableKey)
        );
      }
      return Boolean(getFieldValue(field).trim());
    });

  // Returns ``true`` if the save fully succeeded so callers (the Test
  // Connection button) can chain a follow-up step. Errors are surfaced
  // via toast inside the function — callers should not duplicate them.
  //
  // ``skipActivation`` lets the Test Connection flow persist credentials
  // (so server-side variable_service can resolve them) without switching
  // the active provider — testing should never silently change settings.
  const handleSave = async (options?: {
    silent?: boolean;
    skipActivation?: boolean;
  }): Promise<boolean> => {
    if (selectedProvider.status !== "available") return false;
    if (!canSave) {
      setErrorData({
        title: t("settings.dbProviders.errorMissingConfig"),
        list: [
          `${selectedProvider.label} requires ${selectedProvider.configFields
            .filter(
              (field): field is DBProviderTextField =>
                field.kind !== "boolean" &&
                field.required &&
                !getFieldValue(field).trim(),
            )
            .map((field) => field.label)
            .join(", ")}.`,
        ],
      });
      return false;
    }

    try {
      const fieldsToSave = selectedProvider.configFields.filter((field) => {
        if (field.kind === "boolean") {
          // Persist booleans only when the user actually flipped them
          // this session — otherwise we'd write the default to a
          // global variable on every save, polluting the variables
          // page with values the user never set.
          return field.variableKey in variableValues;
        }
        const nextValue = getFieldValue(field).trim();
        return (
          nextValue && (field.variableKey in variableValues || field.required)
        );
      });

      await Promise.all(
        fieldsToSave.map((field) => {
          const value =
            field.kind === "boolean"
              ? getFieldValue(field) // already "true" / "false"
              : getFieldValue(field).trim();
          return setVariable({
            name: field.variableKey,
            value,
            isSecret: field.kind === "boolean" ? false : field.isSecret,
          });
        }),
      );
      if (!options?.skipActivation) {
        await activateProvider(selectedProvider);
        // Resetting these on a non-activating save would re-snap the
        // selected panel back to the active provider via the
        // ``activeProviderId`` useEffect — that's correct after a real
        // Save, but wrong when we're only persisting credentials for
        // a Test Connection round-trip on a non-active provider.
        setVariableValues({});
        setEditingSecret({});
        setHasManuallySelectedProvider(false);
      }
      if (!options?.silent) {
        setSuccessData({
          title:
            selectedProvider.id === "chroma"
              ? t("settings.dbProviders.chromaSelected")
              : t("settings.dbProviders.configSaved", {
                  provider: selectedProvider.label,
                }),
        });
      }
      return true;
    } catch (error: unknown) {
      setErrorData({
        title: t("settings.dbProviders.errorSaving"),
        list: [getErrorDetail(error)],
      });
      return false;
    }
  };

  const handleTestConnection = async () => {
    if (selectedProvider.status !== "available") return;
    if (!canSave) {
      setErrorData({
        title: t("settings.dbProviders.errorMissingConfig"),
        list: [
          `${selectedProvider.label} requires ${selectedProvider.configFields
            .filter(
              (field): field is DBProviderTextField =>
                field.kind !== "boolean" &&
                field.required &&
                !getFieldValue(field).trim(),
            )
            .map((field) => field.label)
            .join(", ")}.`,
        ],
      });
      return;
    }

    // Build the test payload from current form state BEFORE saving —
    // ``handleSave`` clears ``variableValues`` on success, so reading
    // form values afterward would surface stale globals instead of the
    // user's just-saved draft. The backend_config still references
    // credential VARIABLE NAMES (URL/USERNAME/PASSWORD), so the
    // server-side variable_service lookup happens after Save persists
    // them.
    const literalFields: Record<string, string> = {};
    const booleanFields: Record<string, boolean> = {};
    for (const field of selectedProvider.configFields) {
      const raw = getFieldValue(field);
      if (field.kind === "boolean") {
        booleanFields[field.variableKey] = raw === "true";
      } else {
        literalFields[field.variableKey] = raw.trim();
      }
    }

    // Persist the variables first; the server-side test reads
    // OPENSEARCH_URL etc. through ``variable_service``. Skip the
    // activation step — testing must not switch the active provider.
    const saved = await handleSave({ silent: true, skipActivation: true });
    if (!saved) {
      // ``handleSave`` already surfaced an error toast.
      return;
    }

    try {
      const backendConfig = buildBackendConfigPayload(
        selectedProvider.id as AvailableDBProviderId,
        literalFields,
        booleanFields,
      );
      const response = await testProviderConnection({
        backend_type: toAPIBackendType(
          selectedProvider.id as AvailableDBProviderId,
        ),
        backend_config: backendConfig,
      });
      if (response.ok) {
        // ``setSuccessData`` only takes a title; pack any backend
        // detail (cluster name, version) into the title so it shows.
        setSuccessData({
          title: response.message
            ? t("settings.dbProviders.connectionSuccessfulWith", {
                message: response.message,
              })
            : t("settings.dbProviders.connectionSuccessful"),
        });
      } else {
        setErrorData({
          title: t("settings.dbProviders.connectionFailed"),
          list: [
            response.message || t("settings.dbProviders.connectionRejected"),
          ],
        });
      }
    } catch (error: unknown) {
      setErrorData({
        title: t("settings.dbProviders.errorTesting"),
        list: [getErrorDetail(error)],
      });
    }
  };

  const handleUseChroma = async () => {
    const chromaProvider = DB_PROVIDER_OPTIONS[0];
    try {
      await activateProvider(chromaProvider);
      setSelectedProviderId("chroma");
      setHasManuallySelectedProvider(false);
      setSuccessData({ title: t("settings.dbProviders.chromaSelected") });
    } catch (error: unknown) {
      setErrorData({
        title: t("settings.dbProviders.errorSelectingChroma"),
        list: [getErrorDetail(error)],
      });
    }
  };

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
