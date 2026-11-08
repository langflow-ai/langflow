import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption } from "../../types";
import { isSavedModelUnavailable } from "../saved-model-availability";

const saved: ModelOption = {
  name: "claude-sonnet-5",
  icon: "Anthropic",
  provider: "Anthropic",
  metadata: { model_type: "llm" },
};

const anthropic = (
  overrides: Partial<ModelProviderWithStatus> = {},
): ModelProviderWithStatus => ({
  provider: "Anthropic",
  is_enabled: true,
  is_configured: true,
  models: [{ model_name: "claude-sonnet-5", metadata: {} }],
  ...overrides,
});

const openai: ModelProviderWithStatus = {
  provider: "OpenAI",
  is_enabled: true,
  is_configured: true,
  models: [{ model_name: "gpt-4o-mini", metadata: {} }],
};

const base = {
  savedValue: saved,
  providers: [anthropic(), openai],
  enabledModels: { Anthropic: { "claude-sonnet-5": true } },
  modelStatusIsReliable: true,
};

describe("isSavedModelUnavailable", () => {
  it("is never judged while provider or enabled-model status is still settling", () => {
    expect(
      isSavedModelUnavailable({
        ...base,
        providers: [openai],
        modelStatusIsReliable: false,
      }),
    ).toBe(false);
  });

  it("is false while the saved model is still listed by its configured provider", () => {
    expect(isSavedModelUnavailable(base)).toBe(false);
  });

  it("is true when the saved provider is no longer offered at all", () => {
    // A revoked provider disappears from /models entirely for that user.
    expect(isSavedModelUnavailable({ ...base, providers: [openai] })).toBe(
      true,
    );
    // ...including when no provider is offered to this user at all (an
    // Enterprise install that starts closed): a settled empty list is a
    // verdict, not a still-loading gap.
    expect(
      isSavedModelUnavailable({ ...base, providers: [], enabledModels: {} }),
    ).toBe(true);
  });

  it("is true when a configured provider stopped listing the model and the user's settings never heard of it", () => {
    // Policy hid the model: it is filtered out of the catalog and out of
    // enabled_models rather than reported as disabled.
    expect(
      isSavedModelUnavailable({
        ...base,
        providers: [anthropic({ models: [] }), openai],
        enabledModels: { Anthropic: {}, OpenAI: { "gpt-4o-mini": true } },
      }),
    ).toBe(true);
  });

  it("is false for a model the user deactivated in their own settings", () => {
    // Deactivation keeps the model in enabled_models with `false`; that is the
    // existing "swap to a valid model" path, not a restriction.
    expect(
      isSavedModelUnavailable({
        ...base,
        providers: [anthropic({ models: [] }), openai],
        enabledModels: { Anthropic: { "claude-sonnet-5": false } },
      }),
    ).toBe(false);
  });

  it("is false for a disconnected provider, which keeps its configure affordance", () => {
    expect(
      isSavedModelUnavailable({
        ...base,
        providers: [anthropic({ is_configured: false, models: [] })],
        enabledModels: {},
      }),
    ).toBe(false);
  });

  describe("on a decision field", () => {
    const luna: ModelOption = {
      name: "gpt-6-luna",
      icon: "OpenAI",
      provider: "OpenAI",
      metadata: { model_type: "decision" },
    };
    const openaiListing = (
      models: ModelProviderWithStatus["models"],
    ): ModelProviderWithStatus => ({ ...openai, models });
    const decisionBase = {
      savedValue: luna,
      modelStatusIsReliable: true,
      modelType: "decision" as const,
    };

    it.each([true, false])(
      "checks an unconfigured provider's catalog only when status is reliable: %s",
      (modelStatusIsReliable) => {
        expect(
          isSavedModelUnavailable({
            ...decisionBase,
            modelStatusIsReliable,
            providers: [{ ...openaiListing([]), is_configured: false }],
            enabledModels: { OpenAI: { "gpt-6-luna": false } },
          }),
        ).toBe(modelStatusIsReliable);
      },
    );

    it("keeps an allowed decision model available for provider setup", () => {
      expect(
        isSavedModelUnavailable({
          ...decisionBase,
          providers: [
            {
              ...openaiListing([
                {
                  model_name: "gpt-6-luna",
                  metadata: { model_type: "decision" },
                },
              ]),
              is_configured: false,
            },
          ],
          enabledModels: { OpenAI: { "gpt-6-luna": false } },
        }),
      ).toBe(false);
    });

    it("is not kept available by a chat model of the same name", () => {
      expect(
        isSavedModelUnavailable({
          ...decisionBase,
          providers: [
            openaiListing([
              { model_name: "gpt-6-luna", metadata: { model_type: "llm" } },
            ]),
          ],
          enabledModels: { OpenAI: { "gpt-6-luna": true } },
        }),
      ).toBe(true);
    });

    it("is unavailable once the catalog leaves it out, though the typed map keeps it switched off", () => {
      // Policy-blocked decision rows stay in enabled_models_by_type as false.
      expect(
        isSavedModelUnavailable({
          ...decisionBase,
          providers: [openaiListing([])],
          enabledModels: { OpenAI: { "gpt-6-luna": false } },
        }),
      ).toBe(true);
    });

    it("is available while the catalog lists it as a decision model", () => {
      expect(
        isSavedModelUnavailable({
          ...decisionBase,
          providers: [
            openaiListing([
              {
                model_name: "gpt-6-luna",
                metadata: { model_type: "decision" },
              },
            ]),
          ],
          enabledModels: { OpenAI: {} },
        }),
      ).toBe(false);
    });
  });

  it("cannot judge a legacy name-only value or a missing enabled-models map", () => {
    expect(
      isSavedModelUnavailable({
        ...base,
        savedValue: { ...saved, provider: "" },
        providers: [openai],
      }),
    ).toBe(false);
    expect(
      isSavedModelUnavailable({
        ...base,
        providers: [openai],
        enabledModels: undefined,
      }),
    ).toBe(false);
  });
});
