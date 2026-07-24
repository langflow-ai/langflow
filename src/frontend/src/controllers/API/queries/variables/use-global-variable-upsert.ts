import { VALID_CATEGORIES } from "@/constants/constants";
import { useDeleteGlobalVariables } from "./use-delete-global-variables";
import { useGetGlobalVariables } from "./use-get-global-variables";
import { usePatchGlobalVariables } from "./use-patch-global-variables";
import { usePostGlobalVariables } from "./use-post-global-variables";

type VariableCategory = (typeof VALID_CATEGORIES)[number];

export interface UpsertGlobalVariableParams {
  name: string;
  value: string;
  /** Create-only: the PATCH endpoint does not change a variable's type. */
  type?: string;
  default_fields?: string[];
  category?: VariableCategory;
}

export interface UpsertGlobalVariableResult {
  action: "created" | "updated";
  name: string;
  id: string;
}

/**
 * Wraps the global-variable post/patch/delete mutations behind the shared
 * upsert-by-name rule: an existing name is UPDATED, never duplicate-created
 * (the backend rejects duplicate names with a 400).
 */
export function useGlobalVariableUpsert() {
  const { data: globalVariables } = useGetGlobalVariables();
  const postMutation = usePostGlobalVariables();
  const patchMutation = usePatchGlobalVariables();
  const deleteMutation = useDeleteGlobalVariables();

  const upsertGlobalVariable = async (
    params: UpsertGlobalVariableParams,
  ): Promise<UpsertGlobalVariableResult> => {
    const existing = globalVariables?.find(
      (variable) => variable.name === params.name,
    );

    if (existing) {
      const updateData: {
        id: string;
        value: string;
        default_fields?: string[];
      } = { id: existing.id, value: params.value };
      if (params.default_fields !== undefined) {
        updateData.default_fields = params.default_fields;
      }
      const res = await patchMutation.mutateAsync(updateData);
      return {
        action: "updated",
        name: res?.name ?? params.name,
        id: existing.id,
      };
    }

    const res = await postMutation.mutateAsync({
      name: params.name,
      value: params.value,
      type: params.type,
      default_fields: params.default_fields ?? [],
      category: params.category,
    });
    return { action: "created", name: res.name, id: res.id };
  };

  return {
    upsertGlobalVariable,
    updateGlobalVariable: patchMutation.mutate,
    updateGlobalVariableAsync: patchMutation.mutateAsync,
    deleteGlobalVariable: deleteMutation.mutate,
    deleteGlobalVariableAsync: deleteMutation.mutateAsync,
    isCreating: postMutation.isPending,
    isUpdating: patchMutation.isPending,
    isDeleting: deleteMutation.isPending,
    isPending:
      postMutation.isPending ||
      patchMutation.isPending ||
      deleteMutation.isPending,
  };
}
