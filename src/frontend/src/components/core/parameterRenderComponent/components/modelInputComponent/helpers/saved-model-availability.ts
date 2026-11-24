import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption } from "../types";
import { canonicalProviderName, providerNamesMatch } from "./provider-identity";
import { recoverModelOption } from "./recover-model-option";

type EnabledModels = Record<string, Record<string, boolean>>;

export interface SavedModelAvailabilityParams {
  savedValue: ModelOption | undefined;
  providers: ModelProviderWithStatus[] | undefined;
  enabledModels: EnabledModels | undefined;
  /**
   * Whether both the provider list and the enabled-models map reflect settled
   * server state. While it is false nothing can be judged unavailable — a
   * mid-flight fetch must not be read as "the saved model is gone".
   */
  modelStatusIsReliable: boolean;
}

/**
 * Whether a saved model is no longer offered to this user at all — as opposed
 * to merely not enabled locally (provider present but unconfigured, or the
 * model deactivated in the user's own settings).
 *
 * Two shapes count as unavailable, and both are what an administrator
 * restriction looks like from the builder's seat (LE-1960):
 *
 * - the saved provider is missing from the provider list entirely — it was
 *   never offered to this user, or its approval was revoked;
 * - the saved provider is configured, but its catalog no longer lists the
 *   model and the user's enabled-models map has never heard of it — a model
 *   hidden by policy, removed from the catalog, or no longer served live.
 *
 * The caller decides what to do with the answer: keep the saved value (never
 * silently swap it for another model) and explain the state in the trigger.
 */
export function isSavedModelUnavailable({
  savedValue,
  providers,
  enabledModels,
  modelStatusIsReliable,
}: SavedModelAvailabilityParams): boolean {
  if (!modelStatusIsReliable || !providers || enabledModels === undefined) {
    // Nothing can be judged unavailable until both server views have loaded.
    // A settled, empty provider list is a verdict, not a gap: no provider is
    // offered to this user at all, so a saved one is unavailable like any
    // other missing provider.
    return false;
  }
  const saved = recoverModelOption(savedValue);
  if (!saved?.name || !saved.provider) {
    // Legacy name-only values carry no provider to judge against.
    return false;
  }

  const providerInfo = providers.find((provider) =>
    providerNamesMatch(provider.provider, saved.provider),
  );
  if (!providerInfo) {
    return true;
  }
  if (providerInfo.is_configured !== true) {
    // Unconfigured / disconnected providers keep their existing
    // "configure the provider" affordance.
    return false;
  }
  const listedInCatalog = (providerInfo.models ?? []).some(
    (model) => model.model_name === saved.name,
  );
  if (listedInCatalog) {
    return false;
  }
  const knownToUserSettings =
    (enabledModels?.[saved.provider] !== undefined &&
      Object.hasOwn(enabledModels[saved.provider], saved.name)) ||
    (enabledModels?.[canonicalProviderName(saved.provider)] !== undefined &&
      Object.hasOwn(
        enabledModels[canonicalProviderName(saved.provider)],
        saved.name,
      ));
  return !knownToUserSettings;
}
