import { VALID_CATEGORIES } from "@/constants/constants";
import type { GlobalVariable, TAB_TYPES } from "@/types/global_variables";
import type { ProviderScopeParams } from "../../helpers/provider-scope";
import { usePatchGlobalVariables } from "./use-patch-global-variables";
import { usePostGlobalVariables } from "./use-post-global-variables";

type VariableCategory = (typeof VALID_CATEGORIES)[number];

export interface UpsertGlobalVariableParams {
  name: string;
  value: string;
  /** Create-only: the PATCH endpoint does not change a variable's type. */
  type?: TAB_TYPES;
  default_fields?: string[];
  category?: VariableCategory;
}

export interface UpsertGlobalVariableResult {
  action: "created" | "updated";
  name: string;
  id: string;
}

/**
 * Tags a rejected upsert with the branch that failed ("created" | "updated") so
 * the caller can attribute the error message without re-deriving which path ran.
 */
function withAction(
  error: unknown,
  action: UpsertGlobalVariableResult["action"],
): unknown {
  if (error && typeof error === "object") {
    (error as { action?: UpsertGlobalVariableResult["action"] }).action =
      action;
  }
  return error;
}

/**
 * Wraps the global-variable post/patch mutations behind the shared
 * upsert-by-name rule: an existing name is UPDATED, never duplicate-created
 * (the backend rejects duplicate names with a 400). Deletion is intentionally
 * not part of this façade — the settings page owns it via
 * useDeleteGlobalVariables.
 */
export function useGlobalVariableUpsert(
  providerScope?: ProviderScopeParams,
  // The modal already owns the query. Reusing its settled snapshot avoids a
  // second observer racing the same scoped request when the modal mounts.
  globalVariables?: GlobalVariable[],
) {
  const postMutation = usePostGlobalVariables();
  const patchMutation = usePatchGlobalVariables();

  const upsertGlobalVariable = async (
    params: UpsertGlobalVariableParams,
  ): Promise<UpsertGlobalVariableResult> => {
    const existing = globalVariables?.find(
      (variable) => variable.name === params.name,
    );

    // Only route a same-name request into the PATCH branch when it is safe to
    // do so. The stored type must match the requested one — PATCH cannot change
    // a variable's type, so a mismatch would silently overwrite (e.g.) a Generic
    // variable's value with Credential input and keep it Generic. And the
    // variable must be owned by the current user — a variable only shared to
    // them would PATCH an id they cannot write and surface a misleading 403.
    // Any other case falls through to the create path, where the backend
    // returns its authoritative duplicate-name error instead of this hook
    // mutating data it should not touch.
    if (
      existing &&
      existing.is_owner !== false &&
      (params.type === undefined || existing.type === params.type)
    ) {
      const updateData: {
        id: string;
        value: string;
        default_fields?: string[];
      } = { id: existing.id, value: params.value };
      if (params.default_fields !== undefined) {
        // Union, not replace: the create form only ever carries the field(s)
        // the user just picked, so writing them wholesale would detach the
        // variable from every other field it was already applied to.
        updateData.default_fields = Array.from(
          new Set([
            ...(existing.default_fields ?? []),
            ...params.default_fields,
          ]),
        );
      }
      try {
        // Name and id are already known locally: `existing` was matched by
        // name and PATCH does not change it, so there is no need to read them
        // back from the (loosely typed) patch response. The create branch below
        // reads its response only because the id is server-generated.
        await patchMutation.mutateAsync({
          ...updateData,
          ...(providerScope ?? {}),
        });
        return { action: "updated", name: params.name, id: existing.id };
      } catch (error) {
        throw withAction(error, "updated");
      }
    }

    try {
      const res = await postMutation.mutateAsync({
        name: params.name,
        value: params.value,
        type: params.type,
        default_fields: params.default_fields ?? [],
        category: params.category,
        ...(providerScope ?? {}),
      });
      return { action: "created", name: res.name, id: res.id };
    } catch (error) {
      throw withAction(error, "created");
    }
  };

  return {
    upsertGlobalVariable,
    updateGlobalVariable: (
      params: Parameters<typeof patchMutation.mutate>[0],
      options?: Parameters<typeof patchMutation.mutate>[1],
    ) => patchMutation.mutate({ ...params, ...(providerScope ?? {}) }, options),
  };
}
