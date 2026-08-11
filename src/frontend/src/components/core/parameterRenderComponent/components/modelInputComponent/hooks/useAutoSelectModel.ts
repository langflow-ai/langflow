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
  /**
   * Whether both the provider list and the enabled-models map reflect settled
   * server state. While it is false nothing is auto-selected — a mid-flight
   * fetch must not be read as "the saved model is gone".
   */
  modelStatusIsReliable: boolean;
  hasProcessedEmptyRef: MutableRefObject<boolean>;
}

/**
 * Auto-selects the first available model when the value is empty or the saved
 * value went stale — its provider is known but no longer offers the model,
 * whether it was disconnected or the model deactivated. Extracted from
 * ModelInputComponent (LE-1736 W24); the once-guard ref is shared with
 * deriveSelectedModel (W23) and owned by the component.
 */
export function useAutoSelectModel({
  flatOptions,
  value,
  handleOnNewValue,
  isConnectionMode,
  providers,
  modelStatusIsReliable,
  hasProcessedEmptyRef,
}: UseAutoSelectModelParams): void {
  useEffect(() => {
    if (
      !modelStatusIsReliable ||
      flatOptions.length === 0 ||
      isConnectionMode
    ) {
      return;
    }

    const isEmpty = !value || value.length === 0;

    let isSavedValueStale = false;
    if (!isEmpty) {
      const saved = value[0];
      const inOptions = flatOptions.some((option) =>
        matchesModelIdentity(option, saved),
      );
      // A known provider that no longer offers the model is stale whether it was
      // disconnected or the model deactivated; an unknown one we cannot judge.
      if (!inOptions && saved.provider) {
        isSavedValueStale =
          providers?.some((p) => p.provider === saved.provider) ?? false;
      }
    }

    // The ref debounces the empty-value auto-select only; a value that goes
    // stale mid-session (provider disconnected) must still be replaced.
    if (hasProcessedEmptyRef.current && !isSavedValueStale) return;

    // Sticky-default: if the component has a saved value, keep it as-is. The
    // backend injects any selection that isn't in the user's enabled list
    // back into `options` tagged with `not_enabled_locally`, so the saved
    // value remains visible and runnable. Only auto-select the first option
    // when there's no saved value at all OR when the saved value is stale.
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
  }, [
    flatOptions,
    value,
    handleOnNewValue,
    isConnectionMode,
    providers,
    modelStatusIsReliable,
  ]);
}
