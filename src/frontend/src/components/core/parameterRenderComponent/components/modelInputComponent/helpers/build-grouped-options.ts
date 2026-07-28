import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption } from "../types";

type EnabledModels = Record<string, Record<string, boolean>>;

export interface BuildGroupedOptionsParams {
  options: ModelOption[];
  enabledModels: EnabledModels | undefined;
  providers: ModelProviderWithStatus[] | undefined;
  modelType: string;
  savedValue: ModelOption | undefined;
  modelFilters: Record<string, unknown> | undefined;
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
 * Pure: extracted verbatim from ModelInputComponent's `groupedOptions` memo so
 * the grouping can be unit-tested with fixtures (LE-1736 W22).
 */
export function buildGroupedOptions({
  options,
  enabledModels,
  providers,
  modelType,
  savedValue,
  modelFilters,
}: BuildGroupedOptionsParams): Record<string, ModelOption[]> {
  const grouped: Record<string, ModelOption[]> = {};
  const seen = new Set<string>();

  for (const option of options) {
    if (option.metadata?.is_disabled_provider) continue;
    const provider = option.provider || "Unknown";

    const isStickyNotEnabled = option.metadata?.not_enabled_locally === true;
    if (isStickyNotEnabled) {
      const providerConfigured = providers?.some(
        (p) => p.provider === provider && p.is_configured,
      );
      if (providerConfigured) continue;
    }

    if (!isStickyNotEnabled && enabledModels) {
      const providerModels = enabledModels[provider];
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

  if (enabledModels && providers) {
    for (const providerInfo of providers) {
      const providerName = providerInfo.provider;
      const providerModels = enabledModels[providerName];
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

  const savedKey = savedValue?.name
    ? `${savedValue.provider || "Unknown"}::${savedValue.name}`
    : null;
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
    (Object.keys(grouped).length === 0 || savedInRegistry);
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
