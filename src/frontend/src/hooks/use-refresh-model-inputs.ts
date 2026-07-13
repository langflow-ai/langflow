import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import {
  type RefreshOptions,
  refreshAllModelInputs,
} from "@/services/refresh-model-inputs";

/** @deprecated import from "@/services/refresh-model-inputs" */
export {
  type RefreshOptions,
  refreshAllModelInputs,
} from "@/services/refresh-model-inputs";
/** @deprecated import from "@/utils/model-node-helpers" */
export {
  buildRefreshPayload,
  createUpdatedNode,
  findModelFieldKey,
  isModelNode,
} from "@/utils/model-node-helpers";

/** Hook to refresh all model inputs in the current flow */
export function useRefreshModelInputs() {
  const queryClient = useQueryClient();
  const isRefreshingRef = useRef(false);

  const refresh = useCallback(
    async (options?: RefreshOptions) => {
      if (isRefreshingRef.current) return;
      isRefreshingRef.current = true;

      try {
        await refreshAllModelInputs(queryClient, options);
      } finally {
        isRefreshingRef.current = false;
      }
    },
    [queryClient],
  );

  return {
    refresh,
    refreshAllModelInputs: refresh, // deprecated alias
  };
}
