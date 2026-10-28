import type { EnabledModelsResponse } from "@/controllers/API/queries/models/use-get-enabled-models";
import type { ModelType } from "@/types/models";

/**
 * Resolves model authorization without collapsing same-name LLM and embedding
 * deployments. Once a provider has a typed map, that map is authoritative for
 * every model type; the flat map remains a compatibility fallback only for
 * language and embedding models of providers that have no typed map at all.
 * Decision models never fall back: the flat map predates them and does not
 * record which kind a name was enabled for.
 */
function enabledModelsOfProvider(
  data: EnabledModelsResponse,
  provider: string,
  modelType: ModelType,
): Record<string, boolean> {
  const typedProvider = data.enabled_models_by_type?.[provider];
  if (typedProvider !== undefined) return typedProvider[modelType] ?? {};
  if (modelType === "decision") return {};
  return data.enabled_models[provider] ?? {};
}

export function isModelEnabledForType(
  data: EnabledModelsResponse,
  provider: string,
  modelName: string,
  modelType: ModelType,
): boolean {
  return enabledModelsOfProvider(data, provider, modelType)[modelName] === true;
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
    Array.from(providerNames, (provider) => [
      provider,
      enabledModelsOfProvider(data, provider, modelType),
    ]),
  );
}
