import { useEffect } from "react";
import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import { matchesModelIdentity } from "../helpers/model-option-identity";
import { isSavedModelUnavailable } from "../helpers/saved-model-availability";
import type { ModelOption } from "../types";

export interface UseAutoSelectModelParams {
  flatOptions: ModelOption[];
  /**
   * Raw template options before sticky entries are filtered out of the picker.
   * A saved model present here with `not_enabled_locally` must be preserved —
   * it is blocked or user-disabled, not retired.
   */
  rawOptions?: ModelOption[];
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
 * offers the model (for example after a disconnect). Blocked or user-disabled
 * sticky models (`not_enabled_locally`) are preserved so the flow is not
 * silently rewritten. An empty value is left empty (LE-2168). A model that is
 * no longer offered at all — restricted by an administrator or removed from
 * the catalog — is left in place too, so the restriction stays visible instead
 * of being papered over by a silent swap (LE-1960). Extracted from
 * ModelInputComponent (LE-1736 W24).
 */
export function useAutoSelectModel({
  flatOptions,
  rawOptions,
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
      // A known provider that no longer offers the model is stale when the
      // provider was disconnected or the model truly disappeared. Sticky
      // not_enabled_locally entries for a still-configured provider mean the
      // model is blocked/disabled — keep the saved choice visible. Restricted
      // models (LE-1960) are also left in place so the trigger can name them.
      if (!inOptions && saved.provider) {
        const providerEntry = providers?.find(
          (p) => p.provider === saved.provider,
        );
        if (providerEntry) {
          const stickyPresent = (rawOptions ?? []).some(
            (option) =>
              matchesModelIdentity(option, saved) &&
              option.metadata?.not_enabled_locally === true,
          );
          const preserveBlocked =
            stickyPresent && providerEntry.is_configured === true;
          isSavedValueStale =
            !preserveBlocked &&
            !isSavedModelUnavailable({
              savedValue: saved,
              providers,
              enabledModels,
              modelStatusIsReliable,
            });
        }
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
    rawOptions,
    value,
    handleOnNewValue,
    isConnectionMode,
    providers,
    modelStatusIsReliable,
    enabledModels,
  ]);
}
