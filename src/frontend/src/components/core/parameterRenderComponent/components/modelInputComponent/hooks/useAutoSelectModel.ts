import { type MutableRefObject, useEffect } from "react";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import { matchesModelIdentity } from "../helpers/model-option-identity";
import type { ModelOption } from "../types";

export interface UseAutoSelectModelParams {
  flatOptions: ModelOption[];
  value: ModelOption[] | undefined;
  handleOnNewValue: handleOnNewValueType;
  isConnectionMode: boolean;
  providers: ModelProviderWithStatus[] | undefined;
  hasProcessedEmptyRef: MutableRefObject<boolean>;
}

/**
 * Auto-selects the first available model when the value is empty or the saved
 * value is stale (its provider is configured but the model is gone). Extracted
 * verbatim from ModelInputComponent (LE-1736 W24); the once-guard ref is shared
 * with deriveSelectedModel (W23) and owned by the component.
 */
export function useAutoSelectModel({
  flatOptions,
  value,
  handleOnNewValue,
  isConnectionMode,
  providers,
  hasProcessedEmptyRef,
}: UseAutoSelectModelParams): void {
  useEffect(() => {
    if (flatOptions.length === 0 || isConnectionMode) return;
    if (hasProcessedEmptyRef.current) return;

    const isEmpty = !value || value.length === 0;

    let isSavedValueStale = false;
    if (!isEmpty) {
      const saved = value[0];
      const inOptions = flatOptions.some((option) =>
        matchesModelIdentity(option, saved),
      );
      if (!inOptions && saved.provider) {
        isSavedValueStale =
          providers?.some(
            (p) => p.provider === saved.provider && p.is_configured,
          ) ?? false;
      }
    }

    if (!isEmpty && !isSavedValueStale) return;

    const firstOption = flatOptions[0];
    const newValue = [
      {
        ...(firstOption.id && { id: firstOption.id }),
        name: firstOption.name,
        icon: firstOption.icon || "Bot",
        provider: firstOption.provider || "Unknown",
        metadata: firstOption.metadata ?? {},
      },
    ];
    handleOnNewValue({ value: newValue });
    hasProcessedEmptyRef.current = true;
  }, [flatOptions, value, handleOnNewValue, isConnectionMode, providers]);
}
