import {
  type DBProviderConfigField,
  type DBProviderOption,
  type DBProviderTextField,
  getGlobalVariableValue,
  hasGlobalVariableValue,
  parseBooleanGlobalVariable,
} from "@/constants/dbProviderConstants";
import type { GlobalVariable } from "@/types/global_variables";

/**
 * Field-value resolution and save-gating for the selected provider:
 * session edits (``variableValues``) win over stored globals, which win
 * over field defaults.
 */
export function useDBProviderFields({
  selectedProvider,
  globalVariables,
  variableValues,
}: {
  selectedProvider: DBProviderOption;
  globalVariables: GlobalVariable[];
  variableValues: Record<string, string>;
}) {
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
    hasGlobalVariableValue(globalVariables, variableKey);

  // True when every required field already has a saved variable so the
  // provider can be activated / tested without the user re-entering anything.
  // Secret fields use the API's non-sensitive value-presence signal because
  // API responses mask the value; non-secret fields use the stored value.
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
  // the API confirms the masked variable has a stored value.
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

  return { getFieldValue, hasConfiguredValue, isHydrated, canSave };
}
