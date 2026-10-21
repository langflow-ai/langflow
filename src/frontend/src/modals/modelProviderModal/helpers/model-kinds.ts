import type { ModelType, ModelTypeFilter } from "@/types/models";

/** Every model kind the Model Providers dialog lists, in display order. */
export const MODEL_KINDS: readonly ModelType[] = [
  "llm",
  "embeddings",
  "decision",
];

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

/** Whether a catalog row is of `kind`. */
export function isModelOfKind(
  model: { metadata?: Record<string, unknown> | null },
  kind: ModelType,
): boolean {
  return model.metadata?.model_type === kind;
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
    kinds.some((kind) => isModelOfKind(model, kind)),
  );
}
