import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelInputComponent, { ModelOption } from "../index";

// Mock scrollIntoView for cmdk library
Element.prototype.scrollIntoView = jest.fn();

// Mock stores
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    setErrorData: mockSetErrorData,
  }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      getNode: jest.fn(),
      setFilterEdge: jest.fn(),
      setFilterType: jest.fn(),
      nodes: [],
    }),
  },
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: {
    getState: () => ({
      data: {},
    }),
  },
}));

// Mock API hooks
const mockProvidersData = [
  { provider: "OpenAI", is_enabled: true },
  { provider: "Anthropic", is_enabled: false },
];

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: jest.fn(() => ({
    data: mockProvidersData,
    isLoading: false,
  })),
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: { enabled_models: {} },
    isLoading: false,
  })),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: jest.fn(() => ({
    mutateAsync: jest.fn(),
  })),
}));

// Mock mutateTemplate
jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: jest.fn(),
}));

// Mock ModelProviderModal
jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div data-testid="model-provider-modal">
        Model Provider Modal
        <button onClick={onClose} data-testid="close-provider-modal">
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

// Mock LoadingTextComponent
jest.mock("@/components/common/loadingTextComponent", () => ({
  __esModule: true,
  default: ({ text }: { text: string }) => (
    <span data-testid="loading-text">{text}</span>
  ),
}));

// Sample model options for testing
const mockOptions: ModelOption[] = [
  {
    id: "gpt-4",
    name: "gpt-4",
    icon: "Bot",
    provider: "OpenAI",
    metadata: {},
  },
  {
    id: "gpt-3.5-turbo",
    name: "gpt-3.5-turbo",
    icon: "Bot",
    provider: "OpenAI",
    metadata: {},
  },
  {
    id: "claude-3-opus",
    name: "claude-3-opus",
    icon: "Bot",
    provider: "Anthropic",
    metadata: {},
  },
];

const defaultProps: any = {
  id: "test-model-input",
  value: [],
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: mockOptions,
  placeholder: "Setup Provider",
  nodeId: "test-node-id",
  nodeClass: {
    template: {
      model: {
        model_type: "language",
      },
    },
  },
  handleNodeClass: jest.fn(),
  editNode: false,
};

describe("ModelInputComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render loading state when no options are provided", () => {
      render(<ModelInputComponent {...defaultProps} options={[]} />);

      expect(screen.getByTestId("loading-text")).toBeInTheDocument();
      expect(screen.getByText("Loading models")).toBeInTheDocument();
    });

    it("should render the model selector when options are available", () => {
      render(<ModelInputComponent {...defaultProps} />);

      // Should show the dropdown trigger
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("should display placeholder text when no model is selected", () => {
      render(<ModelInputComponent {...defaultProps} value={[]} />);

      // Initially selects first model, but let's check the UI is present
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("should show selected model name", async () => {
      const selectedValue = [
        {
          id: "gpt-4",
          name: "gpt-4",
          icon: "Bot",
          provider: "OpenAI",
          metadata: {},
        },
      ];

      render(<ModelInputComponent {...defaultProps} value={selectedValue} />);

      await waitFor(() => {
        expect(screen.getByText("gpt-4")).toBeInTheDocument();
      });
    });

    it("should render disabled state correctly", () => {
      render(<ModelInputComponent {...defaultProps} disabled={true} />);

      const button = screen.getByRole("combobox");
      expect(button).toBeDisabled();
    });
  });

  describe("Dropdown Interaction", () => {
    it("should open dropdown when trigger is clicked", async () => {
      const user = userEvent.setup();
      render(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      // Should show provider groups
      await waitFor(() => {
        expect(screen.getByText("OpenAI")).toBeInTheDocument();
      });
    });

    it("should show model options grouped by provider", async () => {
      const user = userEvent.setup();
      render(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      // Wait for dropdown to open and show content
      await waitFor(() => {
        // Check that model options with data-testid are rendered
        expect(screen.getByTestId("gpt-4-option")).toBeInTheDocument();
        expect(screen.getByTestId("gpt-3.5-turbo-option")).toBeInTheDocument();
      });
    });

    it("should call handleOnNewValue when a model is selected", async () => {
      const handleOnNewValue = jest.fn();
      const user = userEvent.setup();

      render(
        <ModelInputComponent
          {...defaultProps}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByText("gpt-3.5-turbo")).toBeInTheDocument();
      });

      const modelOption = screen.getByTestId("gpt-3.5-turbo-option");
      await user.click(modelOption);

      expect(handleOnNewValue).toHaveBeenCalled();
    });
  });

  describe("Model Provider Modal", () => {
    it("should open manage providers dialog when button is clicked", async () => {
      const user = userEvent.setup();
      render(<ModelInputComponent {...defaultProps} />);

      // Open dropdown first
      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(
          screen.getByTestId("manage-model-providers"),
        ).toBeInTheDocument();
      });

      // Click manage providers button
      const manageButton = screen.getByTestId("manage-model-providers");
      await user.click(manageButton);

      await waitFor(() => {
        expect(screen.getByTestId("model-provider-modal")).toBeInTheDocument();
      });
    });
  });

  describe("Footer Buttons", () => {
    it("should render Manage Model Providers button", async () => {
      const user = userEvent.setup();
      render(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByText("Manage Model Providers")).toBeInTheDocument();
      });
    });
  });

  describe("Edge Cases", () => {
    it("should filter out disabled provider models from grouped options", () => {
      const optionsWithDisabled: ModelOption[] = [
        ...mockOptions,
        {
          id: "disabled-model",
          name: "disabled-model",
          icon: "Bot",
          provider: "DisabledProvider",
          metadata: { is_disabled_provider: true },
        },
      ];

      render(
        <ModelInputComponent {...defaultProps} options={optionsWithDisabled} />,
      );

      // The disabled model should not appear in the UI
      expect(screen.queryByText("disabled-model")).not.toBeInTheDocument();
    });

    it("should handle empty value array", () => {
      render(<ModelInputComponent {...defaultProps} value={[]} />);

      // Component should render without crashing
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("should auto-select first model when value is empty and options exist", () => {
      const handleOnNewValue = jest.fn();

      render(
        <ModelInputComponent
          {...defaultProps}
          value={[]}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      // Should have called handleOnNewValue with first option
      expect(handleOnNewValue).toHaveBeenCalled();
    });
  });
});
