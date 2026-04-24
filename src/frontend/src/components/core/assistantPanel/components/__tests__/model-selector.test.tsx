import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelSelector } from "../model-selector";
import type { AssistantModel } from "../../assistant-panel.types";

// --- Mocks ---

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`}>{name}</span>;
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
