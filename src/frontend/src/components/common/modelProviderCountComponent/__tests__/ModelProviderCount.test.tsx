import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import ModelProviderCount from "../index";

// Mock the useGetEnabledModels hook
const mockEnabledModelsData = {
  enabled_models: {},
};

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: mockEnabledModelsData,
    isLoading: false,
    error: null,
  })),
}));

// Mock the ModelProviderModal component
jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div data-testid="model-provider-modal">
        <span>Model Provider Modal</span>
        <button onClick={onClose} data-testid="close-modal-button">
          Close
        </button>
      </div>
    ) : null,
}));

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Custom render helper with TooltipProvider
const renderWithProviders = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

// Helper to update mock data
const setMockEnabledModels = (
  models: Record<string, Record<string, boolean>>,
) => {
  mockEnabledModelsData.enabled_models = models;
};

describe("ModelProviderCount", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setMockEnabledModels({});
  });

  describe("Rendering", () => {
    it("should render the component with default state", () => {
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("Models")).toBeInTheDocument();
      expect(screen.getByTestId("icon-BrainCog")).toBeInTheDocument();
    });

    it("should display count of 0 when no models are enabled", () => {
      setMockEnabledModels({});
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("0")).toBeInTheDocument();
    });

    it("should display correct count for single provider with enabled models", () => {
      setMockEnabledModels({
        openai: {
          "gpt-4": true,
          "gpt-3.5-turbo": true,
          "gpt-4-mini": false,
        },
      });
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("should display correct count across multiple providers", () => {
      setMockEnabledModels({
        openai: {
          "gpt-4": true,
          "gpt-3.5-turbo": true,
        },
        anthropic: {
          "claude-3-opus": true,
          "claude-3-sonnet": false,
        },
        cohere: {
          "command-r": true,
          "command-r-plus": true,
        },
      });
      renderWithProviders(<ModelProviderCount />);

      // 2 openai + 1 anthropic + 2 cohere = 5
      expect(screen.getByText("5")).toBeInTheDocument();
    });

    it("should display count for 10+ enabled models", () => {
      setMockEnabledModels({
        openai: {
          "model-1": true,
          "model-2": true,
          "model-3": true,
          "model-4": true,
          "model-5": true,
        },
        anthropic: {
          "model-6": true,
          "model-7": true,
          "model-8": true,
          "model-9": true,
          "model-10": true,
          "model-11": true,
        },
      });
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("11")).toBeInTheDocument();
    });

    it("should only count enabled models (true values)", () => {
      setMockEnabledModels({
        openai: {
          "enabled-model-1": true,
          "disabled-model-1": false,
          "enabled-model-2": true,
          "disabled-model-2": false,
        },
      });
      renderWithProviders(<ModelProviderCount />);

      // Only count true values
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  describe("Modal Interaction", () => {
    it("should open modal when button is clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<ModelProviderCount />);

      // Modal should not be visible initially
      expect(
        screen.queryByTestId("model-provider-modal"),
      ).not.toBeInTheDocument();

      // Click the button
      const button = screen.getByRole("button");
      await user.click(button);

      // Modal should now be visible
      expect(screen.getByTestId("model-provider-modal")).toBeInTheDocument();
      expect(screen.getByText("Model Provider Modal")).toBeInTheDocument();
    });

    it("should close modal when onClose is called", async () => {
      const user = userEvent.setup();
      renderWithProviders(<ModelProviderCount />);

      // Open the modal
      const button = screen.getByRole("button");
      await user.click(button);

      expect(screen.getByTestId("model-provider-modal")).toBeInTheDocument();

      // Close the modal
      const closeButton = screen.getByTestId("close-modal-button");
      await user.click(closeButton);

      // Modal should be closed
      await waitFor(() => {
        expect(
          screen.queryByTestId("model-provider-modal"),
        ).not.toBeInTheDocument();
      });
    });

    it("should toggle modal open/close on repeated clicks", async () => {
      const user = userEvent.setup();
      renderWithProviders(<ModelProviderCount />);

      const button = screen.getByRole("button");

      // First click - open
      await user.click(button);
      expect(screen.getByTestId("model-provider-modal")).toBeInTheDocument();

      // Second click - close
      await user.click(button);
      await waitFor(() => {
        expect(
          screen.queryByTestId("model-provider-modal"),
        ).not.toBeInTheDocument();
      });

      // Third click - open again
      await user.click(button);
      expect(screen.getByTestId("model-provider-modal")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle undefined enabled_models gracefully", () => {
      mockEnabledModelsData.enabled_models = undefined as any;
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("0")).toBeInTheDocument();
    });

    it("should handle empty providers object", () => {
      setMockEnabledModels({});
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("0")).toBeInTheDocument();
    });

    it("should handle provider with no models", () => {
      setMockEnabledModels({
        openai: {},
        anthropic: {},
      });
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("0")).toBeInTheDocument();
    });

    it("should handle provider with all disabled models", () => {
      setMockEnabledModels({
        openai: {
          "gpt-4": false,
          "gpt-3.5-turbo": false,
        },
      });
      renderWithProviders(<ModelProviderCount />);

      expect(screen.getByText("0")).toBeInTheDocument();
    });
  });

  describe("Accessibility", () => {
    it("should have an accessible button", () => {
      renderWithProviders(<ModelProviderCount />);

      const button = screen.getByRole("button");
      expect(button).toBeInTheDocument();
    });

    it("should include descriptive text for screen readers", () => {
      renderWithProviders(<ModelProviderCount />);

      // The button contains "Models" text
      expect(screen.getByText("Models")).toBeInTheDocument();
    });
  });
});
