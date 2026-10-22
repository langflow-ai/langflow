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
 * The catalog rows the dialog lists for `filter`. Provider badges, the empty
 * state and the model sections all count from this, so a provider never
 * claims models the dialog does not show.
 */
/**
 * Whether a provider with these catalog rows belongs in `filter`'s view: the
 * decision view needs decision models, and the language and embedding views
 * leave out decision-only providers. A provider with no catalog rows yet, such
 * as one discovered live, belongs everywhere but the decision view.
 */
export function providerServesFilter(
  models: readonly { metadata?: Record<string, unknown> | null }[],
  filter: ModelTypeFilter,
): boolean {
  const decisions = modelsOfFilter(models, "decision").length;
  return filter === "decision"
    ? decisions > 0
    : filter === "all" || decisions === 0 || decisions < models.length;
}

export function modelsOfFilter<
  T extends { metadata?: Record<string, unknown> | null },
>(models: readonly T[], filter: ModelTypeFilter): T[] {
  const kinds = kindsOfFilter(filter);
  return models.filter((model) =>
    kinds.includes(model.metadata?.model_type as ModelType),
  );
}
