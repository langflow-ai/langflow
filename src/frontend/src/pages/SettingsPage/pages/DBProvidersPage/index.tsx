import { useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  ACTIVE_DB_PROVIDER_VARIABLE,
  type AvailableDBProviderId,
  DB_PROVIDER_OPTIONS,
  type DBProviderBooleanField,
  type DBProviderConfigField,
  type DBProviderOption,
  type DBProviderTextField,
  getActiveDBProvider,
  getGlobalVariableValue,
  OPENSEARCH_VARIABLES,
  parseBooleanGlobalVariable,
} from "@/constants/dbProviderConstants";
import { VARIABLE_CATEGORY } from "@/constants/providerConstants";
import { useTestDBProviderConnection } from "@/controllers/API/queries/knowledge-bases/use-test-kb-connection";
import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
import type { GlobalVariable } from "@/types/global_variables";
import { cn } from "@/utils/utils";

const MASKED_VALUE = "••••••••";

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
  const { data: globalVariables = [] } = useGetGlobalVariables();
  const [selectedProviderId, setSelectedProviderId] = useState(
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

  const { mutateAsync: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutateAsync: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();
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

  const isPending = isCreating || isUpdating;

  const findVariable = (name: string) =>
    globalVariables.find((variable) => variable.name === name);

  const setVariable = async ({
    name,
    value,
    isSecret,
  }: {
    name: string;
    value: string;
    isSecret: boolean;
  }) => {
    const existingVariable = findVariable(name);
    if (existingVariable) {
      await updateGlobalVariable({ id: existingVariable.id, value });
      return;
    }

    await createGlobalVariable({
      name,
      value,
      type: isSecret ? "Credential" : "Generic",
      category: VARIABLE_CATEGORY.GLOBAL,
      default_fields: [],
    });
  };

  const activateProvider = async (provider: DBProviderOption) => {
    const activeProviderVariable = findVariable(ACTIVE_DB_PROVIDER_VARIABLE);
    if (activeProviderVariable) {
      await updateGlobalVariable({
        id: activeProviderVariable.id,
        value: provider.id,
      });
      return;
    }

    await createGlobalVariable({
      name: ACTIVE_DB_PROVIDER_VARIABLE,
      value: provider.id,
      type: "Generic",
      category: VARIABLE_CATEGORY.SETTINGS,
      default_fields: [],
    });
  };

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

  // Boolean fields always have a defined value (toggle is never blank),
  // so they don't gate the save button — only required text fields do.
  const canSave = selectedProvider.configFields
    .filter(
      (field): field is DBProviderTextField =>
        field.kind !== "boolean" && field.required,
    )
    .every((field) => getFieldValue(field).trim());

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
        title: "Missing required configuration",
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
              ? "Chroma selected"
              : `${selectedProvider.label} configuration saved`,
        });
      }
      return true;
    } catch (error: unknown) {
      setErrorData({
        title: "Error saving DB Provider",
        list: [getErrorDetail(error)],
      });
      return false;
    }
  };

  const handleTestConnection = async () => {
    if (selectedProvider.status !== "available") return;
    if (!canSave) {
      setErrorData({
        title: "Missing required configuration",
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
        backend_type: selectedProvider.id,
        backend_config: backendConfig,
      });
      if (response.ok) {
        // ``setSuccessData`` only takes a title; pack any backend
        // detail (cluster name, version) into the title so it shows.
        setSuccessData({
          title: response.message
            ? `Connection successful — ${response.message}`
            : "Connection successful",
        });
      } else {
        setErrorData({
          title: "Connection failed",
          list: [response.message || "The provider rejected the connection."],
        });
      }
    } catch (error: unknown) {
      setErrorData({
        title: "Error testing provider connection",
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
      setSuccessData({ title: "Chroma selected" });
    } catch (error: unknown) {
      setErrorData({
        title: "Error selecting Chroma",
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
            DB Providers
            <ForwardedIconComponent
              name="Database"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure vector-store providers for Knowledge Bases.
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

// Build a ``backend_config`` payload for ``POST /test-connection`` from
// the in-memory form values, side-stepping the global-variable cache
// which is stale immediately after Save. The server-side test still
// resolves credentials (URL/USERNAME/PASSWORD) through variable_service
// using the variable-name fields below — those names are stable
// constants and don't depend on what the user typed.
function buildBackendConfigPayload(
  providerId: AvailableDBProviderId,
  literalFields: Record<string, string>,
  booleanFields: Record<string, boolean>,
): Record<string, unknown> {
  if (providerId !== "opensearch") {
    return {};
  }
  return {
    url_variable: OPENSEARCH_VARIABLES.URL,
    username_variable: OPENSEARCH_VARIABLES.USERNAME,
    password_variable: OPENSEARCH_VARIABLES.PASSWORD,
    index_name: literalFields[OPENSEARCH_VARIABLES.INDEX_NAME] || "",
    vector_field:
      literalFields[OPENSEARCH_VARIABLES.VECTOR_FIELD] || "chunk_embedding",
    text_field: literalFields[OPENSEARCH_VARIABLES.TEXT_FIELD] || "text",
    use_ssl: booleanFields[OPENSEARCH_VARIABLES.USE_SSL] ?? true,
    verify_certs: booleanFields[OPENSEARCH_VARIABLES.VERIFY_CERTS] ?? true,
  };
}

function ProviderListItem({
  provider,
  isActive,
  isSelected,
  isConfigured,
  onSelect,
}: {
  provider: DBProviderOption;
  isActive: boolean;
  isSelected: boolean;
  isConfigured: boolean;
  onSelect: () => void;
}) {
  const isComingSoon = provider.status === "coming_soon";
  const isMuted = (!isConfigured || isComingSoon) && !provider.defaultEnabled;

  return (
    <button
      type="button"
      data-testid={`db-provider-item-${provider.id}`}
      className={cn(
        "flex w-full cursor-pointer items-center justify-between rounded-lg px-2 py-3 text-left transition-colors hover:bg-muted/50",
        isSelected && "bg-muted/50",
        isComingSoon && "cursor-default opacity-70",
      )}
      onClick={onSelect}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <ForwardedIconComponent
          name={provider.icon}
          className={cn(
            "h-5 w-5 flex-shrink-0",
            isMuted && "opacity-50 grayscale",
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={cn(
              "truncate text-sm font-medium",
              isMuted && "text-muted-foreground",
            )}
          >
            {provider.label}
          </span>
          {isComingSoon && (
            <Badge variant="secondaryStatic" size="sq" className="text-xs">
              Coming soon
            </Badge>
          )}
          {isActive && !isComingSoon && (
            <Badge variant="secondary" size="sq" className="text-xs">
              Active
            </Badge>
          )}
        </div>
      </div>
      {!isComingSoon && (
        <ForwardedIconComponent
          name={isActive ? "Check" : "Plus"}
          className={cn(
            "h-4 w-4",
            isActive ? "text-status-green" : "text-muted-foreground",
          )}
        />
      )}
    </button>
  );
}

function ProviderConfigurationPanel({
  provider,
  activeProviderId,
  globalVariables,
  variableValues,
  editingSecret,
  isPending,
  canSave,
  getFieldValue,
  onVariableChange,
  onSecretEditingChange,
  onSave,
  onTestConnection,
  isTesting,
}: {
  provider: DBProviderOption;
  activeProviderId: "chroma" | "opensearch";
  globalVariables: GlobalVariable[];
  variableValues: Record<string, string>;
  editingSecret: Record<string, boolean>;
  isPending: boolean;
  canSave: boolean;
  getFieldValue: (field: DBProviderConfigField) => string;
  onVariableChange: (key: string, value: string) => void;
  onSecretEditingChange: (key: string, editing: boolean) => void;
  onSave: () => void;
  onTestConnection?: () => void;
  isTesting: boolean;
}) {
  const isComingSoon = provider.status === "coming_soon";
  const isActive = activeProviderId === provider.id;

  return (
    <div className="flex max-w-[680px] flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <ForwardedIconComponent
            name={provider.icon}
            className="h-6 w-6 flex-shrink-0 text-primary"
          />
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold">
                {provider.label}
              </span>
              {isActive && !isComingSoon && (
                <Badge variant="secondary" size="sq" className="text-xs">
                  Active
                </Badge>
              )}
              {isComingSoon && (
                <Badge variant="secondaryStatic" size="sq" className="text-xs">
                  Coming soon
                </Badge>
              )}
            </div>
            <span className="pt-1 text-[13px] text-muted-foreground">
              {provider.description}
            </span>
          </div>
        </div>
      </div>

      {isComingSoon ? (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-[13px] text-muted-foreground">
          This provider is stubbed in the Knowledge Base backend registry and
          will become configurable after the provider implementation is wired
          through end-to-end.
        </div>
      ) : provider.id === "chroma" ? (
        <div className="flex flex-col gap-3">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-[13px] text-muted-foreground">
            Chroma stores vectors on disk next to Langflow and is enabled by
            default. Selecting it here makes it the default provider for new
            Knowledge Bases.
          </div>
          <div className="flex justify-end">
            <Button
              onClick={onSave}
              size="sm"
              loading={isPending}
              disabled={isPending || isActive}
            >
              {isActive ? "Chroma selected" : "Use Chroma"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {provider.configFields.map((field) =>
            field.kind === "boolean" ? (
              <BooleanFieldRow
                key={field.variableKey}
                field={field}
                value={getFieldValue(field) === "true"}
                disabled={isPending}
                onChange={(checked) =>
                  onVariableChange(
                    field.variableKey,
                    checked ? "true" : "false",
                  )
                }
              />
            ) : (
              <TextFieldRow
                key={field.variableKey}
                field={field}
                value={getFieldValue(field)}
                hasNewValue={field.variableKey in variableValues}
                isEditingSecret={Boolean(editingSecret[field.variableKey])}
                existingValue={getGlobalVariableValue(
                  globalVariables,
                  field.variableKey,
                )}
                disabled={isPending}
                onChange={(value) => onVariableChange(field.variableKey, value)}
                onFocus={() => {
                  const existing = getGlobalVariableValue(
                    globalVariables,
                    field.variableKey,
                  );
                  if (
                    field.isSecret &&
                    existing &&
                    !(field.variableKey in variableValues)
                  ) {
                    onSecretEditingChange(field.variableKey, true);
                    onVariableChange(field.variableKey, "");
                  }
                }}
                onBlur={() => {
                  if (!variableValues[field.variableKey]) {
                    onSecretEditingChange(field.variableKey, false);
                  }
                }}
              />
            ),
          )}
          <div className="flex justify-end gap-2">
            {onTestConnection && (
              <Button
                onClick={onTestConnection}
                size="sm"
                variant="outline"
                loading={isTesting}
                disabled={!canSave || isPending || isTesting}
                data-testid="db-provider-test-connection"
              >
                Test connection
              </Button>
            )}
            <Button
              onClick={onSave}
              size="sm"
              loading={isPending}
              disabled={!canSave || isPending || isTesting}
            >
              {isActive ? "Save" : `Save and use ${provider.label}`}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function TextFieldRow({
  field,
  value,
  hasNewValue,
  isEditingSecret,
  existingValue,
  disabled,
  onChange,
  onFocus,
  onBlur,
}: {
  field: DBProviderTextField;
  value: string;
  hasNewValue: boolean;
  isEditingSecret: boolean;
  existingValue: string | undefined;
  disabled: boolean;
  onChange: (value: string) => void;
  onFocus: () => void;
  onBlur: () => void;
}) {
  const inputValue =
    field.isSecret && existingValue && !hasNewValue && !isEditingSecret
      ? MASKED_VALUE
      : value;

  return (
    <label className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-muted-foreground">
        {field.label}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </span>
      <Input
        placeholder={field.placeholder}
        value={inputValue}
        type={
          field.isSecret && (isEditingSecret || hasNewValue)
            ? "password"
            : "text"
        }
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onFocus={onFocus}
        onBlur={onBlur}
      />
      <span className="text-[11px] text-muted-foreground">
        Saved as global variable{" "}
        <span className="font-mono">{field.variableKey}</span>
      </span>
    </label>
  );
}

function BooleanFieldRow({
  field,
  value,
  disabled,
  onChange,
}: {
  field: DBProviderBooleanField;
  value: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-md border border-border bg-muted/20 px-3 py-2">
      <div className="flex min-w-0 flex-col">
        <span className="text-[12px] font-medium">{field.label}</span>
        {field.helperText && (
          <span className="pt-0.5 text-[11px] text-muted-foreground">
            {field.helperText}
          </span>
        )}
        <span className="pt-1 text-[11px] text-muted-foreground">
          Saved as global variable{" "}
          <span className="font-mono">{field.variableKey}</span>
        </span>
      </div>
      <Switch
        checked={value}
        onCheckedChange={onChange}
        disabled={disabled}
        aria-label={field.label}
        data-testid={`db-provider-toggle-${field.variableKey}`}
      />
    </div>
  );
}
