import type { ModelProviderWithStatus } from "@/controllers/API/queries/models/use-get-model-providers";
import type { ModelOption } from "../../types";
import { buildGroupedOptions } from "../build-grouped-options";

const opt = (
  name: string,
  provider: string,
  metadata?: Record<string, unknown>,
): ModelOption => ({
  name,
  provider,
  icon: "Bot",
  ...(metadata && { metadata }),
});

const base = {
  enabledModels: undefined,
  providers: undefined,
  modelType: "llm",
  savedValue: undefined,
  modelFilters: undefined,
  providerStatusIsReliable: false,
} as const;

describe("buildGroupedOptions", () => {
  it("groups options by provider", () => {
    const grouped = buildGroupedOptions({
      ...base,
      options: [
        opt("gpt-4", "OpenAI"),
        opt("claude", "Anthropic"),
        opt("gpt-3", "OpenAI"),
      ],
    });
    expect(Object.keys(grouped).sort()).toEqual(["Anthropic", "OpenAI"]);
    expect(grouped.OpenAI.map((o) => o.name)).toEqual(["gpt-4", "gpt-3"]);
  });

  it("falls back the missing provider to 'Unknown'", () => {
    const grouped = buildGroupedOptions({ ...base, options: [opt("m", "")] });
    expect(grouped.Unknown).toHaveLength(1);
  });

  it("drops an option whose provider enabled-map marks it not-true", () => {
    const grouped = buildGroupedOptions({
      ...base,
      options: [opt("gpt-4", "OpenAI"), opt("gpt-3", "OpenAI")],
      enabledModels: { OpenAI: { "gpt-4": true } },
    });
    expect(grouped.OpenAI.map((o) => o.name)).toEqual(["gpt-4"]);
  });

  it("drops a sticky not_enabled_locally option — it is never selectable", () => {
    const options = [opt("legacy", "OpenAI", { not_enabled_locally: true })];
    expect(buildGroupedOptions({ ...base, options })).toEqual({});

    const withConfiguredProvider = buildGroupedOptions({
      ...base,
      options,
      providers: [
        {
          provider: "OpenAI",
          models: [],
          is_enabled: true,
          is_configured: true,
        },
      ],
      providerStatusIsReliable: true,
    });
    expect(withConfiguredProvider.OpenAI).toBeUndefined();
  });

  it("drops options and registry models of a disconnected provider", () => {
    const providers: ModelProviderWithStatus[] = [
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: false,
        models: [{ model_name: "gpt-4", metadata: { model_type: "llm" } }],
      },
    ];
    const grouped = buildGroupedOptions({
      ...base,
      options: [opt("gpt-4", "OpenAI")],
      providers,
      enabledModels: { OpenAI: { "gpt-4": true } },
      providerStatusIsReliable: true,
    });
    expect(grouped).toEqual({});
  });

  it("keeps the options while the provider status is unreliable", () => {
    const providers: ModelProviderWithStatus[] = [
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: false,
        models: [],
      },
    ];
    const grouped = buildGroupedOptions({
      ...base,
      options: [opt("gpt-4", "OpenAI")],
      providers,
      providerStatusIsReliable: false,
    });
    expect(grouped.OpenAI.map((o) => o.name)).toEqual(["gpt-4"]);
  });

  it("skips is_disabled_provider options", () => {
    const grouped = buildGroupedOptions({
      ...base,
      options: [opt("x", "Foo", { is_disabled_provider: true })],
    });
    expect(grouped).toEqual({});
  });

  it("injects enabled registry models not already present", () => {
    const providers: ModelProviderWithStatus[] = [
      {
        provider: "OpenAI",
        icon: "OpenAiIcon",
        is_enabled: true,
        models: [
          { model_name: "gpt-4", metadata: { model_type: "llm" } },
          { model_name: "gpt-embed", metadata: { model_type: "embeddings" } },
        ],
      },
    ];
    const grouped = buildGroupedOptions({
      ...base,
      options: [],
      providers,
      enabledModels: { OpenAI: { "gpt-4": true, "gpt-embed": true } },
      modelType: "llm",
    });
    // gpt-embed is filtered out by modelType; gpt-4 injected with provider icon
    expect(grouped.OpenAI.map((o) => o.name)).toEqual(["gpt-4"]);
    expect(grouped.OpenAI[0].icon).toBe("OpenAiIcon");
  });

  it("applies modelFilters against option metadata", () => {
    const grouped = buildGroupedOptions({
      ...base,
      options: [
        opt("a", "P", { tier: "pro" }),
        opt("b", "P", { tier: "free" }),
      ],
      modelFilters: { tier: "pro" },
    });
    expect(grouped.P.map((o) => o.name)).toEqual(["a"]);
  });

  it("injects the saved value when its configured provider still lists it", () => {
    const providers: ModelProviderWithStatus[] = [
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
        models: [{ model_name: "saved-model", metadata: {} }],
      },
    ];
    const grouped = buildGroupedOptions({
      ...base,
      options: [],
      providers,
      savedValue: { name: "saved-model", provider: "OpenAI", icon: "Bot" },
      providerStatusIsReliable: true,
    });
    expect(grouped.OpenAI).toHaveLength(1);
    expect(grouped.OpenAI[0].metadata?.not_enabled_locally).toBe(true);
  });

  it("does not inject the saved value of a disconnected provider", () => {
    const providers: ModelProviderWithStatus[] = [
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: false,
        models: [{ model_name: "saved-model", metadata: {} }],
      },
    ];
    const grouped = buildGroupedOptions({
      ...base,
      options: [],
      providers,
      savedValue: { name: "saved-model", provider: "OpenAI", icon: "Bot" },
      providerStatusIsReliable: true,
    });
    expect(grouped).toEqual({});
  });

  it("does not inject the saved value when it is already present", () => {
    const grouped = buildGroupedOptions({
      ...base,
      options: [opt("saved-model", "OpenAI")],
      savedValue: { name: "saved-model", provider: "OpenAI", icon: "Bot" },
    });
    expect(grouped.OpenAI).toHaveLength(1);
    expect(grouped.OpenAI[0].metadata?.not_enabled_locally).toBeUndefined();
  });
});
