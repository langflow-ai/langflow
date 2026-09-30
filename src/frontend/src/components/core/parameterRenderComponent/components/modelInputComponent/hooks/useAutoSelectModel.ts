import { useEffect } from "react";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import { matchesModelIdentity } from "../helpers/model-option-identity";
import { providerNamesMatch } from "../helpers/provider-identity";
import { isSavedModelUnavailable } from "../helpers/saved-model-availability";
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
  /** The user's enabled-models map; a model absent from it (and from the catalog) is restricted, not stale. */
  enabledModels?: Record<string, Record<string, boolean>>;
}

/**
 * Replaces a saved value that went stale — its provider is known but no longer
 * offers the model, whether it was disconnected or the model deactivated. An
 * empty value is left empty (LE-2168). A model that is no longer offered at
 * all — restricted by an administrator or removed from the catalog — is left
 * in place too, so the restriction stays visible instead of being papered
 * over by a silent swap (LE-1960). Extracted from ModelInputComponent
 * (LE-1736 W24).
 */
export function useAutoSelectModel({
  flatOptions,
  value,
  handleOnNewValue,
  isConnectionMode,
  providers,
  modelStatusIsReliable,
  enabledModels,
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
          (providers?.some((p) =>
            providerNamesMatch(p.provider, saved.provider),
          ) ??
            false) &&
          !isSavedModelUnavailable({
            savedValue: saved,
            providers,
            enabledModels,
            modelStatusIsReliable,
          });
      }
    }

    // Only a stale selection is replaced: an unvalidated env-harvested credential
    // already marks a provider enabled, so filling an empty field pre-selected one (LE-2168).
    if (!isSavedValueStale) return;

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
  }, [
    flatOptions,
    value,
    handleOnNewValue,
    isConnectionMode,
    providers,
    modelStatusIsReliable,
    enabledModels,
  ]);
}
