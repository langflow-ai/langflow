import { useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  ACTIVE_KNOWLEDGE_BACKEND_VARIABLE,
  getActiveKnowledgeBackend,
  getGlobalVariableValue,
  KNOWLEDGE_BACKEND_OPTIONS,
  type KnowledgeBackendBooleanField,
  type KnowledgeBackendConfigField,
  type KnowledgeBackendOption,
  type KnowledgeBackendTextField,
  parseBooleanGlobalVariable,
} from "@/constants/knowledgeBackendConstants";
import { VARIABLE_CATEGORY } from "@/constants/providerConstants";
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

export default function KnowledgeBackendsPage() {
  const { data: globalVariables = [] } = useGetGlobalVariables();
  const [selectedBackendId, setSelectedBackendId] = useState(
    getActiveKnowledgeBackend(globalVariables),
  );
  const [hasManuallySelectedBackend, setHasManuallySelectedBackend] =
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

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const activeBackendId = useMemo(
    () => getActiveKnowledgeBackend(globalVariables),
    [globalVariables],
  );

  useEffect(() => {
    if (!hasManuallySelectedBackend) {
      setSelectedBackendId(activeBackendId);
    }
  }, [activeBackendId, hasManuallySelectedBackend]);

  const selectedBackend =
    KNOWLEDGE_BACKEND_OPTIONS.find(
      (backend) => backend.id === selectedBackendId,
    ) ?? KNOWLEDGE_BACKEND_OPTIONS[0];

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

  const activateBackend = async (backend: KnowledgeBackendOption) => {
    const activeBackendVariable = findVariable(
      ACTIVE_KNOWLEDGE_BACKEND_VARIABLE,
    );
    if (activeBackendVariable) {
      await updateGlobalVariable({
        id: activeBackendVariable.id,
        value: backend.id,
      });
      return;
    }

    await createGlobalVariable({
      name: ACTIVE_KNOWLEDGE_BACKEND_VARIABLE,
      value: backend.id,
      type: "Generic",
      category: VARIABLE_CATEGORY.SETTINGS,
      default_fields: [],
    });
  };

  const getFieldValue = (field: KnowledgeBackendConfigField): string => {
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
  const canSave = selectedBackend.configFields
    .filter(
      (field): field is KnowledgeBackendTextField =>
        field.kind !== "boolean" && field.required,
    )
    .every((field) => getFieldValue(field).trim());

  const handleSave = async () => {
    if (selectedBackend.status !== "available") return;
    if (!canSave) {
      setErrorData({
        title: "Missing required configuration",
        list: [
          `${selectedBackend.label} requires ${selectedBackend.configFields
            .filter(
              (field): field is KnowledgeBackendTextField =>
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

    try {
      const fieldsToSave = selectedBackend.configFields.filter((field) => {
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
      await activateBackend(selectedBackend);
      setVariableValues({});
      setEditingSecret({});
      setHasManuallySelectedBackend(false);
      setSuccessData({
        title:
          selectedBackend.id === "chroma"
            ? "Chroma selected"
            : `${selectedBackend.label} configuration saved`,
      });
    } catch (error: unknown) {
      setErrorData({
        title: "Error saving knowledge backend",
        list: [getErrorDetail(error)],
      });
    }
  };

  const handleUseChroma = async () => {
    const chromaBackend = KNOWLEDGE_BACKEND_OPTIONS[0];
    try {
      await activateBackend(chromaBackend);
      setSelectedBackendId("chroma");
      setHasManuallySelectedBackend(false);
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
            Knowledge Backends
            <ForwardedIconComponent
              name="Database"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure vector-store backends for Knowledge Bases.
          </p>
        </div>
      </div>

      <div className="flex h-[calc(100vh-305px)] w-full overflow-hidden rounded-lg border">
        <div
          className={cn(
            "flex flex-col gap-1 p-2 transition-all duration-300 ease-in-out",
            selectedBackend ? "w-1/3 border-r" : "w-full",
          )}
        >
          {KNOWLEDGE_BACKEND_OPTIONS.map((backend) => (
            <BackendListItem
              key={backend.id}
              backend={backend}
              isActive={activeBackendId === backend.id}
              isSelected={selectedBackend.id === backend.id}
              isConfigured={
                backend.id === "chroma" ||
                backend.configFields
                  .filter(
                    (field): field is KnowledgeBackendTextField =>
                      field.kind !== "boolean" && field.required,
                  )
                  .every((field) => hasConfiguredValue(field.variableKey))
              }
              onSelect={() => {
                setHasManuallySelectedBackend(true);
                setSelectedBackendId(backend.id);
              }}
            />
          ))}
        </div>

        <div className="flex min-h-0 w-2/3 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4">
            <BackendConfigurationPanel
              backend={selectedBackend}
              activeBackendId={activeBackendId}
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
                selectedBackend.id === "chroma" ? handleUseChroma : handleSave
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function BackendListItem({
  backend,
  isActive,
  isSelected,
  isConfigured,
  onSelect,
}: {
  backend: KnowledgeBackendOption;
  isActive: boolean;
  isSelected: boolean;
  isConfigured: boolean;
  onSelect: () => void;
}) {
  const isComingSoon = backend.status === "coming_soon";

  return (
    <button
      type="button"
      data-testid={`knowledge-backend-item-${backend.id}`}
      className={cn(
        "flex w-full cursor-pointer items-center justify-between rounded-lg px-2 py-3 text-left transition-colors hover:bg-muted/50",
        isSelected && "bg-muted/50",
        isComingSoon && "cursor-default opacity-70",
      )}
      onClick={onSelect}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <ForwardedIconComponent
          name={backend.icon}
          className={cn(
            "h-5 w-5 flex-shrink-0",
            !isConfigured && !backend.defaultEnabled && "opacity-50 grayscale",
          )}
        />
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={cn(
              "truncate text-sm font-medium",
              !isConfigured &&
                !backend.defaultEnabled &&
                "text-muted-foreground",
            )}
          >
            {backend.label}
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

function BackendConfigurationPanel({
  backend,
  activeBackendId,
  globalVariables,
  variableValues,
  editingSecret,
  isPending,
  canSave,
  getFieldValue,
  onVariableChange,
  onSecretEditingChange,
  onSave,
}: {
  backend: KnowledgeBackendOption;
  activeBackendId: "chroma" | "opensearch";
  globalVariables: GlobalVariable[];
  variableValues: Record<string, string>;
  editingSecret: Record<string, boolean>;
  isPending: boolean;
  canSave: boolean;
  getFieldValue: (field: KnowledgeBackendConfigField) => string;
  onVariableChange: (key: string, value: string) => void;
  onSecretEditingChange: (key: string, editing: boolean) => void;
  onSave: () => void;
}) {
  const isComingSoon = backend.status === "coming_soon";
  const isActive = activeBackendId === backend.id;

  return (
    <div className="flex max-w-[680px] flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <ForwardedIconComponent
            name={backend.icon}
            className="h-6 w-6 flex-shrink-0 text-primary"
          />
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold">{backend.label}</span>
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
              {backend.description}
            </span>
          </div>
        </div>
      </div>

      {isComingSoon ? (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-[13px] text-muted-foreground">
          This backend is stubbed in the Knowledge Base backend registry and
          will become configurable after the provider implementation is wired
          through end-to-end.
        </div>
      ) : backend.id === "chroma" ? (
        <div className="flex flex-col gap-3">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-[13px] text-muted-foreground">
            Chroma stores vectors on disk next to Langflow and is enabled by
            default. Selecting it here makes it the default backend for new
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
          {backend.configFields.map((field) =>
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
          <div className="flex justify-end">
            <Button
              onClick={onSave}
              size="sm"
              loading={isPending}
              disabled={!canSave || isPending}
            >
              {isActive ? "Save" : `Save and use ${backend.label}`}
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
  field: KnowledgeBackendTextField;
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
  field: KnowledgeBackendBooleanField;
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
        data-testid={`knowledge-backend-toggle-${field.variableKey}`}
      />
    </div>
  );
}
