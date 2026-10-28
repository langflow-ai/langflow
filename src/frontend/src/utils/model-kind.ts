import type { ModelType } from "@/types/models";

/** A model field's backend `model_type` mapped to the kind the providers API uses. */
const KIND_BY_FIELD_MODEL_TYPE: Readonly<Record<string, ModelType>> = {
  language: "llm",
  embedding: "embeddings",
  decision: "decision",
};

/**
 * The model kind a model field serves. A field without `model_type` is a
 * language field, the backend default. An unrecognized `model_type` returns
 * null so callers refuse it instead of guessing a kind: a guess would offer
 * models the field cannot run.
 */
export function modelKindOfField(field: unknown): ModelType | null {
  const raw = (field as { model_type?: unknown } | null | undefined)
    ?.model_type;
  if (raw === undefined || raw === null) return "llm";
  if (typeof raw !== "string" || !Object.hasOwn(KIND_BY_FIELD_MODEL_TYPE, raw))
    return null;
  return KIND_BY_FIELD_MODEL_TYPE[raw];
}

/**
 * Decision models are never filled, swapped or cleared on the user's behalf:
 * the chosen provider receives the flow's messages, so only the user picks it.
 */
export function isUserOwnedModelKind(kind: ModelType | null): boolean {
  return kind === "decision";
}
