import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type AvailableDBProviderId,
  type DBProviderConfigField,
  type DBProviderOption,
  getGlobalVariableValue,
} from "@/constants/dbProviderConstants";
import type { GlobalVariable } from "@/types/global_variables";
import { BooleanFieldRow } from "./BooleanFieldRow";
import { TextFieldRow } from "./TextFieldRow";

export function ProviderConfigurationPanel({
  provider,
  activeProviderId,
  globalVariables,
  variableValues,
  editingSecret,
  isPending,
  canSave,
  isHydrated,
  getFieldValue,
  onVariableChange,
  onSecretEditingChange,
  onSave,
  onTestConnection,
  isTesting,
}: {
  provider: DBProviderOption;
  activeProviderId: AvailableDBProviderId;
  globalVariables: GlobalVariable[];
  variableValues: Record<string, string>;
  editingSecret: Record<string, boolean>;
  isPending: boolean;
  canSave: boolean;
  isHydrated: boolean;
  getFieldValue: (field: DBProviderConfigField) => string;
  onVariableChange: (key: string, value: string) => void;
  onSecretEditingChange: (key: string, editing: boolean) => void;
  onSave: () => void;
  onTestConnection?: () => void;
  isTesting: boolean;
}) {
  const { t } = useTranslation();
  const isComingSoon = provider.status === "coming_soon";
  const isActive = activeProviderId === provider.id;
  // True when the user has interacted with any field this session.
  const hasUnsavedChanges = Object.keys(variableValues).length > 0;
  // Label for the primary action button:
  // · Active provider → "Save" (persist any edits)
  // · Hydrated + no edits → "Use <Provider>" (just switch active provider)
  // · Otherwise → "Save and use <Provider>" (persist + activate)
  const saveButtonLabel = isActive
    ? t("settings.dbProviders.save")
    : isHydrated && !hasUnsavedChanges
      ? t("settings.dbProviders.useProvider", { provider: provider.label })
      : t("settings.dbProviders.saveAndUseProvider", {
          provider: provider.label,
        });

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
                  {t("settings.dbProviders.active")}
                </Badge>
              )}
              {isComingSoon && (
                <Badge variant="secondaryStatic" size="sq" className="text-xs">
                  {t("settings.dbProviders.comingSoon")}
                </Badge>
              )}
            </div>
            <span className="pt-1 text-[13px] text-muted-foreground">
              {t(`settings.dbProviders.providers.${provider.id}.description`, {
                defaultValue: provider.description,
              })}
            </span>
          </div>
        </div>
      </div>

      {isComingSoon ? (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-[13px] text-muted-foreground">
          {t("settings.dbProviders.comingSoonDescription")}
        </div>
      ) : provider.id === "chroma" ? (
        <div className="flex flex-col gap-3">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-[13px] text-muted-foreground">
            {t("settings.dbProviders.chromaDescription")}
          </div>
          <div className="flex justify-end">
            <Button
              onClick={onSave}
              size="sm"
              loading={isPending}
              disabled={isPending || isActive}
            >
              {isActive
                ? t("settings.dbProviders.chromaSelected")
                : t("settings.dbProviders.useChroma")}
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
                isSecretConfigured={
                  field.isSecret &&
                  globalVariables.some((v) => v.name === field.variableKey)
                }
                disabled={isPending}
                onChange={(value) => onVariableChange(field.variableKey, value)}
                onFocus={() => {
                  // Use variable existence (not its returned value) as the
                  // gate — credential-type variables may have their value
                  // masked in the API response.
                  const isConfigured =
                    field.isSecret &&
                    globalVariables.some((v) => v.name === field.variableKey);
                  if (isConfigured && !(field.variableKey in variableValues)) {
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
                {t("settings.dbProviders.testConnection")}
              </Button>
            )}
            <Button
              onClick={onSave}
              size="sm"
              loading={isPending}
              disabled={!canSave || isPending || isTesting}
            >
              {saveButtonLabel}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
