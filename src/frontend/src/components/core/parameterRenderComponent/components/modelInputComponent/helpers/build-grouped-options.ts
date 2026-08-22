import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption } from "../types";

type EnabledModels = Record<string, Record<string, boolean>>;

/**
 * Type-aware counterpart of {@link EnabledModels}, keyed
 * provider -> model type -> name -> enabled.
 */
type EnabledModelsByType = Record<
  string,
  Partial<Record<string, Record<string, boolean>>>
>;

export interface BuildGroupedOptionsParams {
  options: ModelOption[];
  enabledModels: EnabledModels | undefined;
  /**
   * Per-type enabled-models map, authoritative for any provider it lists.
   * `enabledModels` merges `llm` and `embeddings` into a single record, so a
   * model enabled for chat also reads as enabled for embeddings there. Older
   * servers omit this map, leaving the flat one as the only available signal.
   */
  enabledModelsByType: EnabledModelsByType | undefined;
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
  enabledModelsByType,
  providers,
  modelType,
  savedValue,
  modelFilters,
  providerStatusIsReliable,
}: BuildGroupedOptionsParams): Record<string, ModelOption[]> {
  const grouped: Record<string, ModelOption[]> = {};
  const seen = new Set<string>();

  const hasEnabledStatus = !!enabledModels || !!enabledModelsByType;

  /**
   * Enabled-status record to filter `providerName` against. Prefers the typed
   * map so a model enabled for another type cannot pass as enabled for this
   * one. A provider listed there but carrying no entry for `modelType` has
   * nothing enabled for it, hence `{}` — filtering every candidate out rather
   * than falling through to the type-agnostic map.
   */
  const enabledStatusFor = (
    providerName: string,
  ): Record<string, boolean> | undefined => {
    const typed = enabledModelsByType?.[providerName];
    if (typed) return typed[modelType] ?? {};
    return enabledModels?.[providerName];
  };
  const disconnectedProviders = new Set(
    providerStatusIsReliable
      ? (providers ?? [])
          .filter((provider) => provider.is_configured === false)
          .map((provider) => provider.provider)
      : [],
  );

  for (const option of options) {
    if (option.metadata?.is_disabled_provider) continue;
    const provider = option.provider || "Unknown";
    if (disconnectedProviders.has(provider)) continue;

    // Sticky-default entries only let the trigger name the saved model;
    // they are never selectable, disconnected or merely deactivated.
    if (option.metadata?.not_enabled_locally === true) continue;

    // Filter against client-side enabled models data. This is the source of
    // truth for what the current user has enabled — stale `options` saved in
    // an imported flow may include models from providers the current user
    // hasn't enabled (e.g. WatsonX). When the provider is tracked in the
    // enabled-status map, the model must be explicitly enabled (=== true); a
    // `false` or missing entry means the model should be hidden.
    if (hasEnabledStatus) {
      const providerModels = enabledStatusFor(provider);
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
    seen.add(`${provider}::${option.name}`);
  }

  if (hasEnabledStatus && providers) {
    for (const providerInfo of providers) {
      const providerName = providerInfo.provider;
      if (disconnectedProviders.has(providerName)) continue;
      const providerModels = enabledStatusFor(providerName);
      if (!providerModels) continue;

      for (const model of providerInfo.models ?? []) {
        const modelName = model.model_name;
        if (providerModels[modelName] !== true) continue;

        // Weaker second line of defence: live discovery stamps each model with
        // the type that was requested, so against an OpenAI-compatible
        // endpoint every candidate claims `modelType` and this cannot separate
        // them on its own — `enabledStatusFor` is what actually scopes them.
        const modelMetadata = (model.metadata ?? {}) as Record<string, unknown>;
        const modelMetadataType = modelMetadata.model_type;
        if (
          typeof modelMetadataType === "string" &&
          modelMetadataType !== modelType
        ) {
          continue;
        }

        if (!passesModelFilters(modelMetadata, modelFilters)) continue;

        const key = `${providerName}::${modelName}`;
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
    ? `${savedValue.provider || "Unknown"}::${savedValue.name}`
    : null;
  const savedProviderConfigured =
    providerStatusIsReliable &&
    (providers?.some(
      (p) => p.provider === savedValue?.provider && p.is_configured,
    ) ??
      false);
  const savedInRegistry =
    !!savedValue?.name &&
    (providers?.some(
      (p) =>
        p.provider === savedValue.provider &&
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
