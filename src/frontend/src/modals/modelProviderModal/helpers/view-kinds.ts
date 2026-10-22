import type { ModelType, ModelTypeFilter } from "@/types/models";

/** Every model kind the Model Providers dialog lists, in display order. */
const MODEL_KINDS: readonly ModelType[] = ["llm", "embeddings", "decision"];

/** Kinds that can be added as free-text deployments (Azure AI Foundry). */
const DEPLOYMENT_KINDS: readonly ModelType[] = ["llm", "embeddings"];

/** The kinds the dialog lists when opened for `filter`. */
export function kindsOfFilter(filter: ModelTypeFilter): readonly ModelType[] {
  return filter === "all" ? MODEL_KINDS : [filter];
}

/** The listed kinds that a provider can also serve as custom deployments. */
export function deploymentKindsOfFilter(filter: ModelTypeFilter): ModelType[] {
  return kindsOfFilter(filter).filter((kind) =>
    DEPLOYMENT_KINDS.includes(kind),
  );
}

/**
 * Whether a provider with these catalog rows belongs in `filter`'s view: the
 * decision view needs decision models, and the language and embedding views
 * leave out decision-only providers. An empty list belongs there only when the
 * provider discovers its models live: policy can empty a decision-only
 * provider's list too. A provider sent without a list is taken to serve
 * language and embedding models, as before decision models.
 */
export function providerServesFilter(
  models: readonly { metadata?: Record<string, unknown> | null }[] | undefined,
  filter: ModelTypeFilter,
  liveDiscovery = false,
): boolean {
  if (filter === "all") return true;
  if (models === undefined) return filter !== "decision";
  if (models.length === 0) return filter !== "decision" && liveDiscovery;
  const decisions = modelsOfFilter(models, "decision").length;
  return filter === "decision" ? decisions > 0 : decisions < models.length;
}

/**
 * The catalog rows the dialog lists for `filter`. Provider badges, the empty
 * state and the model sections all count from this, so a provider never
 * claims models the dialog does not show.
 */
export function modelsOfFilter<
  T extends { metadata?: Record<string, unknown> | null },
>(models: readonly T[], filter: ModelTypeFilter): T[] {
  const kinds = kindsOfFilter(filter);
  return models.filter((model) =>
    kinds.includes(model.metadata?.model_type as ModelType),
  );
}
