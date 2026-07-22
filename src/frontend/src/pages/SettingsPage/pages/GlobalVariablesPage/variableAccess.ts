import type { GlobalVariable } from "@/types/global_variables";

type PermissionCheck = (resourceId: string, action: string) => boolean;

interface VariablePermissionState {
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly permissions: Record<string, readonly string[]> | undefined;
}

export function canMutateVariable(
  variable: GlobalVariable | undefined,
  action: "write" | "delete",
  state: VariablePermissionState,
  can: PermissionCheck,
): boolean {
  if (!variable || state.isLoading) return false;
  if (variable.is_owner === false) {
    const id = variable.id.toLowerCase();
    if (state.isError || !state.permissions || !(id in state.permissions))
      return false;
  }
  return can(variable.id, action);
}

export function authorizedVariableIds(
  variableIds: readonly string[],
  variables: readonly GlobalVariable[] | undefined,
  action: "write" | "delete",
  state: VariablePermissionState,
  can: PermissionCheck,
): string[] {
  const variablesById = new Map(
    variables?.map((variable) => [variable.id, variable]) ?? [],
  );
  return variableIds.filter((id) =>
    canMutateVariable(variablesById.get(id), action, state, can),
  );
}

export const canShareVariable = (
  variable: GlobalVariable | undefined,
): boolean => variable?.can_manage_shares === true;

export function formatVariableValue(
  variable: GlobalVariable | undefined,
  value: unknown,
  sharedLabel: string,
): string {
  if (variable?.is_owner === false) return sharedLabel;
  if (variable?.type === "Credential") return "*****";
  return value === null || value === undefined ? "" : String(value);
}
