import { renderHook } from "@testing-library/react";
import { useAutoSelectModel } from "../useAutoSelectModel";

/**
 * LE-2168: a fresh Language Model / Agent node pre-selected `flatOptions[0]`.
 * Providers count as enabled as soon as a credential exists — Langflow harvests
 * GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY from the environment and
 * never validates them — so an empty field advertised a provider the user never
 * set up (Gemini when only Google was present, Claude when Anthropic sorted first).
 */

const ANTHROPIC = {
  name: "claude-opus-5",
  provider: "Anthropic",
  icon: "Anthropic",
  metadata: {},
};
const OPENAI = {
  name: "gpt-4o-mini",
  provider: "OpenAI",
  icon: "OpenAI",
  metadata: {},
};

const PROVIDERS = [
  { provider: "Anthropic", is_configured: true, is_enabled: true },
  { provider: "OpenAI", is_configured: true, is_enabled: true },
] as never;

const renderAutoSelect = (
  overrides: Partial<Parameters<typeof useAutoSelectModel>[0]> = {},
) => {
  const handleOnNewValue = jest.fn();

  renderHook(() =>
    useAutoSelectModel({
      flatOptions: [ANTHROPIC, OPENAI],
      value: [],
      handleOnNewValue,
      isConnectionMode: false,
      providers: PROVIDERS,
      modelStatusIsReliable: true,
      ...overrides,
    }),
  );

  return handleOnNewValue;
};

describe("useAutoSelectModel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_not_select_a_model_when_the_field_is_empty", () => {
    expect(renderAutoSelect()).not.toHaveBeenCalled();
  });

  it("should_not_select_a_model_when_the_value_is_undefined", () => {
    expect(renderAutoSelect({ value: undefined })).not.toHaveBeenCalled();
  });

  it("should_keep_a_valid_selection_untouched", () => {
    expect(renderAutoSelect({ value: [OPENAI] })).not.toHaveBeenCalled();
  });

  it("should_replace_a_selection_whose_provider_no_longer_offers_it", () => {
    const handleOnNewValue = renderAutoSelect({
      value: [{ ...ANTHROPIC, name: "claude-retired" }],
    });

    expect(handleOnNewValue).toHaveBeenCalledTimes(1);
    expect(handleOnNewValue.mock.calls[0][0].value[0].name).toBe(
      "claude-opus-5",
    );
  });

  it("should_not_act_while_provider_status_is_still_loading", () => {
    const handleOnNewValue = renderAutoSelect({
      value: [{ ...ANTHROPIC, name: "claude-retired" }],
      modelStatusIsReliable: false,
    });

    expect(handleOnNewValue).not.toHaveBeenCalled();
  });
});
