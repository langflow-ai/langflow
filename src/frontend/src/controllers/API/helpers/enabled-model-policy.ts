import type { EnabledModelsResponse } from "@/controllers/API/queries/models/use-get-enabled-models";
import type { ModelType } from "@/types/models";

/**
 * Resolves model authorization without collapsing same-name LLM and embedding
 * deployments. Once a provider has a typed map, that map is authoritative for
 * every model type; the flat map remains a compatibility fallback only for
 * providers that have no typed map at all.
 */
export function isModelEnabledForType(
  data: EnabledModelsResponse,
  provider: string,
  modelName: string,
  modelType: ModelType,
): boolean {
  const typedProvider = data.enabled_models_by_type?.[provider];
  if (typedProvider !== undefined) {
    return typedProvider[modelType]?.[modelName] === true;
  }
  return data.enabled_models[provider]?.[modelName] === true;
}

export function getEnabledModelsForType(
  data: EnabledModelsResponse,
  modelType: ModelType,
): Record<string, Record<string, boolean>> {
  const providerNames = new Set([
    ...Object.keys(data.enabled_models),
    ...Object.keys(data.enabled_models_by_type ?? {}),
  ]);

  return Object.fromEntries(
    Array.from(providerNames, (provider) => {
      const typedProvider = data.enabled_models_by_type?.[provider];
      return [
        provider,
        typedProvider !== undefined
          ? (typedProvider[modelType] ?? {})
          : (data.enabled_models[provider] ?? {}),
      ];
    }),
  );
}
