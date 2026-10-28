import { isUserOwnedModelKind, modelKindOfField } from "../model-kind";

describe("modelKindOfField", () => {
  it.each([
    ["language", "llm"],
    ["embedding", "embeddings"],
    ["decision", "decision"],
  ])("maps a %s field to the %s kind", (modelType, kind) => {
    expect(modelKindOfField({ model_type: modelType })).toBe(kind);
  });

  it("treats a field without model_type as a language field, the backend default", () => {
    expect(modelKindOfField({})).toBe("llm");
    expect(modelKindOfField({ model_type: null })).toBe("llm");
    expect(modelKindOfField(undefined)).toBe("llm");
  });

  // An unknown kind used to fall back to embeddings, which is why the Decision
  // Model component showed "No Models Enabled".
  it.each([
    ["an unknown kind", "rerank"],
    ["a provider-side spelling", "embeddings"],
    ["a different case", "Decision"],
    ["an empty string", ""],
    ["an inherited key", "toString"],
    ["the prototype key", "__proto__"],
  ])("refuses %s instead of guessing", (_label, modelType) => {
    expect(modelKindOfField({ model_type: modelType })).toBeNull();
  });

  it("refuses a model_type that is not a string", () => {
    expect(modelKindOfField({ model_type: 1 })).toBeNull();
    expect(modelKindOfField({ model_type: ["decision"] })).toBeNull();
  });
});

describe("isUserOwnedModelKind", () => {
  it("is true only for decision models", () => {
    expect(isUserOwnedModelKind("decision")).toBe(true);
    expect(isUserOwnedModelKind("llm")).toBe(false);
    expect(isUserOwnedModelKind("embeddings")).toBe(false);
    expect(isUserOwnedModelKind(null)).toBe(false);
  });
});
