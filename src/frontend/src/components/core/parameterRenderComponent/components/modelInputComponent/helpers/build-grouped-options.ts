import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption } from "../types";
import { canonicalProviderName, providerNamesMatch } from "./provider-identity";

type EnabledModels = Record<string, Record<string, boolean>>;

export interface BuildGroupedOptionsParams {
  options: ModelOption[];
  enabledModels: EnabledModels | undefined;
  providers: ModelProviderWithStatus[] | undefined;
  modelType: string;
  savedValue: ModelOption | undefined;
  modelFilters: Record<string, unknown> | undefined;
  /**
   * Whether `providers` reflects settled server state (not fetching, no error).
   * While it is false the connection status cannot be trusted, so no option is
   * dropped for being disconnected.
   */
  providerStatusIsReliable: boolean;
}

function passesModelFilters(
  metadata: Record<string, unknown> | undefined | null,
  modelFilters: Record<string, unknown> | undefined,
): boolean {
  if (!modelFilters) return true;
  if (!metadata) return false;
  for (const [key, expected] of Object.entries(modelFilters)) {
    if (metadata[key] !== expected) return false;
  }
  return true;
}

/**
 * Groups the model options by provider, applying the enabled-models map, the
 * per-node model filters and the model-type filter, and injecting both the
 * registry models and the saved value when they are not otherwise present.
 *
 * Providers reported as disconnected contribute nothing — neither their own
 * options nor a saved value pointing at them.
 *
 * Pure: extracted from ModelInputComponent's `groupedOptions` memo so the
 * grouping can be unit-tested with fixtures (LE-1736 W22).
 */
export function buildGroupedOptions({
  options,
  enabledModels,
  providers,
  modelType,
  savedValue,
  modelFilters,
  providerStatusIsReliable,
}: BuildGroupedOptionsParams): Record<string, ModelOption[]> {
  const grouped: Record<string, ModelOption[]> = {};
  const seen = new Set<string>();
  const authorizedProviders = new Set(
    providerStatusIsReliable
      ? (providers ?? []).map((provider) =>
          canonicalProviderName(provider.provider),
        )
      : [],
  );
  const disconnectedProviders = new Set(
    providerStatusIsReliable
      ? (providers ?? [])
          .filter((provider) => provider.is_configured === false)
          .map((provider) => canonicalProviderName(provider.provider))
      : [],
  );

  for (const option of options) {
    if (option.metadata?.is_disabled_provider) continue;
    const provider = option.provider || "Unknown";
    const providerIdentity = canonicalProviderName(provider);
    if (
      providerStatusIsReliable &&
      !authorizedProviders.has(providerIdentity)
    ) {
      continue;
    }
    if (disconnectedProviders.has(providerIdentity)) continue;

    // Sticky-default entries only let the trigger name the saved model;
    // they are never selectable, disconnected or merely deactivated.
    if (option.metadata?.not_enabled_locally === true) continue;

    // Filter against client-side enabled models data. This is the source of
    // truth for what the current user has enabled — stale `options` saved in
    // an imported flow may include models from providers the current user
    // hasn't enabled (e.g. WatsonX). When the provider is tracked in
    // enabled_models, the model must be explicitly enabled (=== true); a
    // `false` or missing entry means the model should be hidden.
    if (enabledModels) {
      const providerModels =
        enabledModels[provider] ?? enabledModels[providerIdentity];
      if (providerModels && providerModels[option.name] !== true) {
        continue;
      }
    }

    if (
      !passesModelFilters(
        option.metadata as Record<string, unknown> | undefined,
        modelFilters,
      )
    ) {
      continue;
    }

    if (!grouped[provider]) {
      grouped[provider] = [];
    }
    grouped[provider].push(option);
    seen.add(`${providerIdentity}::${option.name}`);
  }

  if (enabledModels && providers) {
    for (const providerInfo of providers) {
      const providerName = providerInfo.provider;
      const providerIdentity = canonicalProviderName(providerName);
      if (disconnectedProviders.has(providerIdentity)) continue;
      const providerModels =
        enabledModels[providerName] ?? enabledModels[providerIdentity];
      if (!providerModels) continue;

      for (const model of providerInfo.models ?? []) {
        const modelName = model.model_name;
        if (providerModels[modelName] !== true) continue;

        const modelMetadata = (model.metadata ?? {}) as Record<string, unknown>;
        const modelMetadataType = modelMetadata.model_type;
        if (
          typeof modelMetadataType === "string" &&
          modelMetadataType !== modelType
        ) {
          continue;
        }

        if (!passesModelFilters(modelMetadata, modelFilters)) continue;

        const key = `${providerIdentity}::${modelName}`;
        if (seen.has(key)) continue;
        seen.add(key);

        if (!grouped[providerName]) {
          grouped[providerName] = [];
        }
        grouped[providerName].push({
          name: modelName,
          icon: providerInfo.icon || "Bot",
          provider: providerName,
          metadata: modelMetadata,
        });
      }
    }
  }

  // Keeps an Assistant-applied registry model selectable while it is missing
  // from enabled_models; a disconnected provider must inject nothing.
  const savedKey = savedValue?.name
    ? `${canonicalProviderName(savedValue.provider || "Unknown")}::${savedValue.name}`
    : null;
  const savedProviderConfigured =
    providerStatusIsReliable &&
    (providers?.some(
      (p) =>
        !!savedValue?.provider &&
        providerNamesMatch(p.provider, savedValue.provider) &&
        p.is_configured,
    ) ??
      false);
  const savedInRegistry =
    !!savedValue?.name &&
    (providers?.some(
      (p) =>
        providerNamesMatch(p.provider, savedValue.provider) &&
        (p.models ?? []).some((m) => m.model_name === savedValue.name),
    ) ??
      false);
  const shouldInjectSaved =
    !!savedValue?.name &&
    !!savedKey &&
    !seen.has(savedKey) &&
    savedProviderConfigured &&
    savedInRegistry;
  if (shouldInjectSaved && savedValue) {
    const providerName = savedValue.provider || "Unknown";
    grouped[providerName] = grouped[providerName] ?? [];
    grouped[providerName].push({
      ...(savedValue.id && { id: savedValue.id }),
      name: savedValue.name,
      icon: savedValue.icon || "Bot",
      provider: providerName,
      metadata: {
        ...(savedValue.metadata ?? {}),
        not_enabled_locally: true,
      },
    } as ModelOption);
  }

  return grouped;
}
