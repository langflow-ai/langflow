import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption, SelectedModel } from "../types";
import { matchesModelIdentity } from "./model-option-identity";
import { providerNamesMatch } from "./provider-identity";
import { recoverModelOption } from "./recover-model-option";
import { isSavedModelUnavailable } from "./saved-model-availability";

export interface DeriveSelectedModelParams {
  isConnectionMode: boolean;
  /** Resolved `t("modelInput.connectOtherModels")` label. */
  connectLabel: string;
  /** External node icon; falls back to "CornerDownLeft". */
  connectIcon: string | undefined;
  savedValue: ModelOption | undefined;
  flatOptions: ModelOption[];
  providers: ModelProviderWithStatus[] | undefined;
  /**
   * Whether `providers` reflects settled server state (not fetching, no error).
   * While it is false the saved provider's `is_configured` is not read at all;
   * the status stays unknown and the saved value renders through the
   * not-enabled-locally trigger.
   */
  providerStatusIsReliable: boolean;
  /** The user's enabled-models map; lets a restricted model be told apart from a deactivated one. */
  enabledModels?: Record<string, Record<string, boolean>>;
  /** Whether `providers` AND `enabledModels` are settled; gates the unavailable branch. */
  modelStatusIsReliable?: boolean;
}

/**
 * Derives the currently selected model shown in the trigger. Pure: extracted
 * verbatim from ModelInputComponent's `selectedModel` memo (LE-1736 W23).
 */
export function deriveSelectedModel({
  isConnectionMode,
  connectLabel,
  connectIcon,
  savedValue,
  flatOptions,
  providers,
  providerStatusIsReliable,
  enabledModels,
  modelStatusIsReliable = false,
}: DeriveSelectedModelParams): SelectedModel | null {
  if (isConnectionMode) {
    return {
      name: connectLabel,
      icon: connectIcon || "CornerDownLeft",
      provider: "",
    } as SelectedModel;
  }

  const saved = recoverModelOption(savedValue);
  const currentName = saved?.name;
  if (!currentName) {
    // Showing flatOptions[0] here would advertise a provider the field is not
    // actually set to, which is how the pre-selection surfaced (LE-2168).
    return null;
  }

  const match = flatOptions.find((option) =>
    matchesModelIdentity(option, saved),
  );
  if (match) return match;

  // A model that is no longer offered at all (restricted by an administrator,
  // removed from the catalog) keeps naming itself in the trigger, flagged so
  // the trigger can explain why — showing flatOptions[0] here would present a
  // model the field is not set to, and "Select a model" would hide the
  // restriction entirely (LE-1960).
  if (
    saved &&
    isSavedModelUnavailable({
      savedValue,
      providers,
      enabledModels,
      modelStatusIsReliable,
    })
  ) {
    // Drop a backend-injected `not_enabled_locally` tag: that flag drives the
    // "configure this provider" wrench, which has nothing to configure here.
    const { not_enabled_locally: _notEnabledLocally, ...savedMetadata } =
      saved.metadata ?? {};
    return {
      ...(saved.id && { id: saved.id }),
      name: saved.name,
      icon: saved.icon || "Bot",
      provider: saved.provider || "Unknown",
      metadata: {
        ...savedMetadata,
        unavailable: true,
      },
    } as SelectedModel;
  }

  if (saved) {
    const savedProviderConfigured = providerStatusIsReliable
      ? providers?.some(
          (p) =>
            providerNamesMatch(p.provider, saved.provider) && p.is_configured,
        )
      : undefined;
    if (!savedProviderConfigured) {
      return {
        ...(saved.id && { id: saved.id }),
        name: saved.name,
        icon: saved.icon || "Bot",
        provider: saved.provider || "Unknown",
        metadata: {
          ...(saved.metadata ?? {}),
          not_enabled_locally: true,
        },
      } as SelectedModel;
    }
  }

  return flatOptions.length > 0 ? flatOptions[0] : null;
}
