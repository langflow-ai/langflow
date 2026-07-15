import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AssistantModel } from "../../assistant-panel.types";
import { ModelSelector } from "../model-selector";

// --- Mocks ---

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`}>{name}</span>;
  };
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: { type: "3rdParty", init: jest.fn() },
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refresh: jest.fn(),
    refreshAllModelInputs: jest.fn(),
  }),
}));

jest.mock("@/modals/modelProviderModal", () => {
  return function MockModelProviderModal({ open }: { open: boolean }) {
    return open ? <div data-testid="mock-model-provider-modal" /> : null;
  };
});

let mockFilteredProviders = [
  {
    provider: "Anthropic",
    icon: "Anthropic",
    models: [
      { model_name: "claude-sonnet-4-20250514" },
      { model_name: "claude-haiku-4-20250514" },
    ],
  },
  {
    provider: "OpenAI",
    icon: "OpenAI",
    models: [{ model_name: "gpt-4o" }],
  },
];

jest.mock("../../hooks", () => ({
  useEnabledModels: () => ({
    filteredProviders: mockFilteredProviders,
    isLoading: false,
  }),
}));

describe("ModelSelector", () => {
  const defaultProps = {
    onModelChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("provider icon in trigger button", () => {
    it("should_display_selected_provider_icon_when_non_openai_provider_is_selected", () => {
      // Arrange — Anthropic model is selected
      const anthropicModel: AssistantModel = {
        id: "Anthropic-claude-sonnet-4-20250514",
        name: "claude-sonnet-4-20250514",
        provider: "Anthropic",
        displayName: "claude-sonnet-4-20250514",
      };

      // Act
      render(
        <ModelSelector selectedModel={anthropicModel} {...defaultProps} />,
      );

      // Assert — the trigger button should show the Anthropic icon
      const triggerButton = screen.getByTestId("assistant-model-selector");
      expect(triggerButton).toHaveTextContent("claude-sonnet-4-20250514");

      // The provider icon should be rendered in the trigger (not just a static "AI" label)
      const providerIcon = screen.getByTestId("icon-Anthropic");
      expect(triggerButton).toContainElement(providerIcon);
    });

    it("should_display_openai_icon_when_openai_provider_is_selected", () => {
      // Arrange — OpenAI model is selected
      const openaiModel: AssistantModel = {
        id: "OpenAI-gpt-4o",
        name: "gpt-4o",
        provider: "OpenAI",
        displayName: "gpt-4o",
      };

      // Act
      render(<ModelSelector selectedModel={openaiModel} {...defaultProps} />);

      // Assert — the trigger button should show the OpenAI icon
      const triggerButton = screen.getByTestId("assistant-model-selector");
      const providerIcon = screen.getByTestId("icon-OpenAI");
      expect(triggerButton).toContainElement(providerIcon);
    });

    it("should_update_provider_icon_when_switching_from_openai_to_anthropic", async () => {
      // Arrange — start with OpenAI selected
      const openaiModel: AssistantModel = {
        id: "OpenAI-gpt-4o",
        name: "gpt-4o",
        provider: "OpenAI",
        displayName: "gpt-4o",
      };

      const onModelChange = jest.fn();

      const { rerender } = render(
        <ModelSelector
          selectedModel={openaiModel}
          onModelChange={onModelChange}
        />,
      );

      // Act — open dropdown and select Anthropic model
      const triggerButton = screen.getByTestId("assistant-model-selector");
      await userEvent.click(triggerButton);
      await userEvent.click(screen.getByText("claude-sonnet-4-20250514"));

      // Assert — onModelChange was called with Anthropic provider
      expect(onModelChange).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "Anthropic",
          name: "claude-sonnet-4-20250514",
        }),
      );

      // Rerender with the new model to verify icon updates
      const anthropicModel: AssistantModel = {
        id: "Anthropic-claude-sonnet-4-20250514",
        name: "claude-sonnet-4-20250514",
        provider: "Anthropic",
        displayName: "claude-sonnet-4-20250514",
      };

      rerender(
        <ModelSelector
          selectedModel={anthropicModel}
          onModelChange={onModelChange}
        />,
      );

      // The trigger button should now show the Anthropic icon
      const updatedTrigger = screen.getByTestId("assistant-model-selector");
      const anthropicIcon = screen.getByTestId("icon-Anthropic");
      expect(updatedTrigger).toContainElement(anthropicIcon);
    });
  });

  describe("out-of-the-box default model (LE-1767)", () => {
    it("should_auto_select_first_strong_model_when_a_weak_model_comes_first_in_catalog_order", () => {
      // Arrange — QA repro: weak model first in catalog order, no stored selection
      mockFilteredProviders = [
        {
          provider: "OpenAI",
          icon: "OpenAI",
          models: [{ model_name: "gpt-4o-mini" }, { model_name: "gpt-4o" }],
        },
      ];

      const onModelChange = jest.fn();

      // Act — fresh user: nothing in localStorage → selectedModel is null
      render(
        <ModelSelector selectedModel={null} onModelChange={onModelChange} />,
      );

      // Assert — the strong model is picked, not allModels[0]
      expect(onModelChange).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "OpenAI", name: "gpt-4o" }),
      );
      expect(
        screen.queryByTestId("assistant-model-weak-hint"),
      ).not.toBeInTheDocument();
    });

    it("should_auto_select_strong_model_from_later_provider_when_first_provider_only_has_weak_models", () => {
      // Arrange — first provider offers only a weak SKU; strong model lives in the next provider
      mockFilteredProviders = [
        {
          provider: "OpenAI",
          icon: "OpenAI",
          models: [{ model_name: "gpt-4o-mini" }],
        },
        {
          provider: "Anthropic",
          icon: "Anthropic",
          models: [{ model_name: "claude-sonnet-4-20250514" }],
        },
      ];

      const onModelChange = jest.fn();

      // Act
      render(
        <ModelSelector selectedModel={null} onModelChange={onModelChange} />,
      );

      // Assert
      expect(onModelChange).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "Anthropic",
          name: "claude-sonnet-4-20250514",
        }),
      );
    });

    it("should_fall_back_to_first_model_and_show_hint_when_every_enabled_model_is_weak", () => {
      // Arrange — user enabled only weak SKUs; there is no strong model to prefer
      mockFilteredProviders = [
        {
          provider: "OpenAI",
          icon: "OpenAI",
          models: [
            { model_name: "gpt-4o-mini" },
            { model_name: "gpt-4.1-nano" },
          ],
        },
      ];

      const onModelChange = jest.fn();

      // Act
      render(
        <ModelSelector selectedModel={null} onModelChange={onModelChange} />,
      );

      // Assert — degrades to today's behavior: first enabled model, hint visible
      expect(onModelChange).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "OpenAI", name: "gpt-4o-mini" }),
      );
      expect(
        screen.getByTestId("assistant-model-weak-hint"),
      ).toBeInTheDocument();
    });

    it("should_not_override_an_explicit_weak_selection_the_user_made", () => {
      // Arrange — the user deliberately picked the weak model; the default must not fight them
      mockFilteredProviders = [
        {
          provider: "OpenAI",
          icon: "OpenAI",
          models: [{ model_name: "gpt-4o-mini" }, { model_name: "gpt-4o" }],
        },
      ];

      const weakModel: AssistantModel = {
        id: "OpenAI-gpt-4o-mini",
        name: "gpt-4o-mini",
        provider: "OpenAI",
        displayName: "gpt-4o-mini",
      };

      const onModelChange = jest.fn();

      // Act
      render(
        <ModelSelector
          selectedModel={weakModel}
          onModelChange={onModelChange}
        />,
      );

      // Assert — selection is respected; the advisory hint still shows
      expect(onModelChange).not.toHaveBeenCalled();
      expect(
        screen.getByTestId("assistant-model-weak-hint"),
      ).toBeInTheDocument();
    });
  });

  describe("stale model from localStorage", () => {
    it("should_auto_select_first_available_model_when_selected_provider_is_no_longer_available", () => {
      // Arrange — only Anthropic is configured, but selectedModel is a stale OpenAI model from localStorage
      mockFilteredProviders = [
        {
          provider: "Anthropic",
          icon: "Anthropic",
          models: [
            { model_name: "claude-sonnet-4-20250514" },
            { model_name: "claude-haiku-4-20250514" },
          ],
        },
      ];

      const staleModel: AssistantModel = {
        id: "OpenAI-gpt-5.4",
        name: "gpt-5.4",
        provider: "OpenAI",
        displayName: "gpt-5.4",
      };

      const onModelChange = jest.fn();

      // Act
      render(
        <ModelSelector
          selectedModel={staleModel}
          onModelChange={onModelChange}
        />,
      );

      // Assert — onModelChange should have been called with the first available model (Anthropic)
      expect(onModelChange).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "Anthropic",
          name: "claude-sonnet-4-20250514",
        }),
      );
    });

    it("should_auto_select_first_available_model_when_selected_model_is_no_longer_in_provider", () => {
      // Arrange — OpenAI is configured, but the specific model no longer exists
      mockFilteredProviders = [
        {
          provider: "OpenAI",
          icon: "OpenAI",
          models: [{ model_name: "gpt-4o" }],
        },
      ];

      const staleModel: AssistantModel = {
        id: "OpenAI-gpt-5.4",
        name: "gpt-5.4",
        provider: "OpenAI",
        displayName: "gpt-5.4",
      };

      const onModelChange = jest.fn();

      // Act
      render(
        <ModelSelector
          selectedModel={staleModel}
          onModelChange={onModelChange}
        />,
      );

      // Assert — onModelChange should have been called with a valid model
      expect(onModelChange).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "OpenAI",
          name: "gpt-4o",
        }),
      );
    });
  });
});
