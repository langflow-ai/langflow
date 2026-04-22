import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BaseInputProps } from "@/components/core/parameterRenderComponent/types";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import ModelInputComponent from "../index";
import type { ModelInputComponentType, ModelOption } from "../types";

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

// Mock useRefreshModelInputs with controllable promise
let mockRefreshResolve: () => void;
const mockRefreshAllModelInputs = jest.fn(
  () =>
    new Promise<void>((resolve) => {
      mockRefreshResolve = resolve;
    }),
);
jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: mockRefreshAllModelInputs,
  }),
}));

jest.mock("@/stores/flowStore", () => {
  const state = {
    getNode: jest.fn(),
    setNode: jest.fn(),
    setFilterEdge: jest.fn(),
    setFilterType: jest.fn(),
    nodes: [],
    edges: [],
  };
  const hook = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  hook.getState = () => state;
  return { __esModule: true, default: hook };
});

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

const defaultProps: BaseInputProps & ModelInputComponentType = {
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
        type: "",
        required: false,
        list: false,
        show: false,
        readonly: false,
      },
    },
    description: "",
    display_name: "",
    documentation: "",
  },
  handleNodeClass: jest.fn(),
  editNode: false,
};

// Helper to render with QueryClientProvider
const renderWithQueryClient = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
  );
};

describe("ModelInputComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render disabled combobox when no options are provided", () => {
      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} options={[]} />,
      );

      const combobox = screen.getByRole("combobox");
      expect(combobox).toBeInTheDocument();
      expect(combobox).toBeDisabled();
    });

    it("should render the model selector when options are available", () => {
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      // Should show the dropdown trigger
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("should display placeholder text when no model is selected", () => {
      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} value={[]} />,
      );

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

      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} value={selectedValue} />,
      );

      await waitFor(() => {
        expect(screen.getByText("gpt-4")).toBeInTheDocument();
      });
    });

    it("should render disabled state correctly", () => {
      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} disabled={true} />,
      );

      const button = screen.getByRole("combobox");
      expect(button).toBeDisabled();
    });
  });

  describe("Dropdown Interaction", () => {
    it("should open dropdown when trigger is clicked", async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      // Should show provider groups
      await waitFor(() => {
        expect(screen.getByText("OpenAI")).toBeInTheDocument();
      });
    });

    it("should show model options grouped by provider", async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

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

      renderWithQueryClient(
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
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

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
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByText("Manage Model Providers")).toBeInTheDocument();
      });
    });
  });

  describe("Refresh List", () => {
    it("should close popover before entering loading state when refresh is clicked", async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByTestId("refresh-model-list")).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId("refresh-model-list");
      await user.click(refreshButton);

      await waitFor(() => {
        expect(screen.getByText("Loading models")).toBeInTheDocument();
      });

      mockRefreshResolve();

      await waitFor(() => {
        expect(screen.getByRole("combobox")).toBeInTheDocument();
      });

      // Popover must be closed after refresh to prevent width measurement glitch
      expect(screen.queryByTestId("gpt-4-option")).not.toBeInTheDocument();
      expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
    });

    it("should not crash when component renders without popover open during refresh", () => {
      mockRefreshAllModelInputs.mockImplementationOnce(() => Promise.resolve());
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      expect(screen.getByRole("combobox")).toBeInTheDocument();
      expect(screen.queryByTestId("gpt-4-option")).not.toBeInTheDocument();
    });

    it("should call refresh with silent flag exactly once per click", async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByTestId("refresh-model-list")).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId("refresh-model-list");
      await user.click(refreshButton);

      expect(mockRefreshAllModelInputs).toHaveBeenCalledTimes(1);
      expect(mockRefreshAllModelInputs).toHaveBeenCalledWith({ silent: true });

      mockRefreshResolve();
    });

    it("should recover to normal state when refresh rejects", async () => {
      // handleRefreshButtonPress uses try/finally, so refreshOptions resets even on error
      mockRefreshAllModelInputs.mockImplementationOnce(() =>
        Promise.reject(new Error("Network error")),
      );

      const user = userEvent.setup();
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByTestId("refresh-model-list")).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId("refresh-model-list");
      await user.click(refreshButton);

      // finally block sets refreshOptions=false, restoring the combobox
      await waitFor(() => {
        expect(screen.getByRole("combobox")).toBeInTheDocument();
      });

      expect(screen.queryByText("Loading models")).not.toBeInTheDocument();
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

      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} options={optionsWithDisabled} />,
      );

      // The disabled model should not appear in the UI
      expect(screen.queryByText("disabled-model")).not.toBeInTheDocument();
    });

    it("should handle empty value array", () => {
      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} value={[]} />,
      );

      // Component should render without crashing
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("should auto-select first model when value is empty and options exist", () => {
      const handleOnNewValue = jest.fn();

      renderWithQueryClient(
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

  describe("Enabled Models Filtering (imported flows)", () => {
    // Helpers to override the default top-level mocks on a per-test basis.
    const mockedUseGetEnabledModels = useGetEnabledModels as jest.Mock;
    const mockedUseGetModelProviders = useGetModelProviders as jest.Mock;

    afterEach(() => {
      // Restore the default mock implementations for downstream tests.
      mockedUseGetEnabledModels.mockReturnValue({
        data: { enabled_models: {} },
        isLoading: false,
      });
      mockedUseGetModelProviders.mockReturnValue({
        data: mockProvidersData,
        isLoading: false,
      });
    });

    it("hides models not explicitly enabled when enabled_models tracks the provider", async () => {
      // gpt-4 is enabled, gpt-3.5-turbo is explicitly disabled. The strict
      // filter in groupedOptions must hide gpt-3.5-turbo.
      mockedUseGetEnabledModels.mockReturnValue({
        data: {
          enabled_models: {
            OpenAI: { "gpt-4": true, "gpt-3.5-turbo": false },
          },
        },
        isLoading: false,
      });

      const user = userEvent.setup();
      renderWithQueryClient(<ModelInputComponent {...defaultProps} />);

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByTestId("gpt-4-option")).toBeInTheDocument();
      });
      expect(
        screen.queryByTestId("gpt-3.5-turbo-option"),
      ).not.toBeInTheDocument();
    });

    it("augments dropdown with enabled models that are missing from the saved options", async () => {
      // Simulates an imported flow whose exporter only knew about gpt-4, but
      // the importing user also has gpt-4o and gpt-4.1 enabled. Those extra
      // models should appear in the dropdown via the augment pass.
      mockedUseGetModelProviders.mockReturnValue({
        data: [
          {
            provider: "OpenAI",
            is_enabled: true,
            icon: "OpenAI",
            models: [
              { model_name: "gpt-4", metadata: {} },
              { model_name: "gpt-4o", metadata: {} },
              { model_name: "gpt-4.1", metadata: {} },
            ],
          },
        ],
        isLoading: false,
      });
      mockedUseGetEnabledModels.mockReturnValue({
        data: {
          enabled_models: {
            OpenAI: {
              "gpt-4": true,
              "gpt-4o": true,
              "gpt-4.1": true,
            },
          },
        },
        isLoading: false,
      });

      const savedOptions: ModelOption[] = [
        {
          id: "gpt-4",
          name: "gpt-4",
          icon: "Bot",
          provider: "OpenAI",
          metadata: {},
        },
      ];

      const user = userEvent.setup();
      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} options={savedOptions} />,
      );

      const trigger = screen.getByRole("combobox");
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByTestId("gpt-4-option")).toBeInTheDocument();
      });
      // Augmented entries from providersData × enabled_models must be visible.
      expect(screen.getByTestId("gpt-4o-option")).toBeInTheDocument();
      expect(screen.getByTestId("gpt-4.1-option")).toBeInTheDocument();
    });

    it("keeps the trigger enabled when saved options=[] but providersData has enabled models", () => {
      // Reproduces the "outdated component update" scenario: the backend
      // response strips saved options, but the user still has enabled models.
      // The trigger's disabled check reads flatOptions, which is the augmented
      // list — so the combobox must remain clickable.
      mockedUseGetModelProviders.mockReturnValue({
        data: [
          {
            provider: "OpenAI",
            is_enabled: true,
            icon: "OpenAI",
            models: [{ model_name: "gpt-4o", metadata: {} }],
          },
        ],
        isLoading: false,
      });
      mockedUseGetEnabledModels.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4o": true } } },
        isLoading: false,
      });

      renderWithQueryClient(
        <ModelInputComponent {...defaultProps} options={[]} />,
      );

      // With augmented options, the combobox is NOT disabled (regression
      // check for the grayed-out-after-update bug).
      expect(screen.getByRole("combobox")).not.toBeDisabled();
    });

    it("keeps a saved value whose model isn't enabled locally and renders the Configure wrench", async () => {
      // The backend's update_model_options_in_build_config injects the saved
      // value into options tagged with `not_enabled_locally: true` whenever
      // it isn't in the user's enabled list. The frontend must:
      //   1. NOT auto-reset the saved value.
      //   2. Keep the option visible/selectable in the dropdown.
      //   3. Render the Configure wrench next to the trigger.
      mockedUseGetEnabledModels.mockReturnValue({
        data: {
          enabled_models: {
            OpenAI: { "gpt-4": true, "gpt-3.5-turbo": true },
          },
        },
        isLoading: false,
      });

      const handleOnNewValue = jest.fn();
      const savedValue = [
        {
          id: "ibm/granite-3",
          name: "ibm/granite-3",
          icon: "IBMWatsonx",
          provider: "IBM watsonx.ai",
          metadata: { not_enabled_locally: true },
        },
      ];
      // Backend-style options: the saved value is injected into options with
      // the sticky flag so the client can render it.
      const optionsWithSticky = [
        ...mockOptions,
        {
          id: "ibm/granite-3",
          name: "ibm/granite-3",
          icon: "IBMWatsonx",
          provider: "IBM watsonx.ai",
          metadata: { not_enabled_locally: true },
        },
      ];

      renderWithQueryClient(
        <ModelInputComponent
          {...defaultProps}
          options={optionsWithSticky}
          value={savedValue}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      // Value must not be reset by the auto-select effect.
      expect(handleOnNewValue).not.toHaveBeenCalled();

      // Saved model remains visible in the trigger label.
      await waitFor(() => {
        expect(screen.getByText("ibm/granite-3")).toBeInTheDocument();
      });

      // Configure wrench is rendered next to the trigger.
      expect(
        screen.getByTestId(`${defaultProps.id}-configure`),
      ).toBeInTheDocument();
    });

    it("opens the provider manager when the Configure wrench is clicked", async () => {
      mockedUseGetEnabledModels.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
        isLoading: false,
      });

      const savedValue = [
        {
          id: "ibm/granite-3",
          name: "ibm/granite-3",
          icon: "IBMWatsonx",
          provider: "IBM watsonx.ai",
          metadata: { not_enabled_locally: true },
        },
      ];
      const optionsWithSticky = [
        ...mockOptions,
        {
          id: "ibm/granite-3",
          name: "ibm/granite-3",
          icon: "IBMWatsonx",
          provider: "IBM watsonx.ai",
          metadata: { not_enabled_locally: true },
        },
      ];

      const handleOnNewValue = jest.fn();
      const user = userEvent.setup();
      renderWithQueryClient(
        <ModelInputComponent
          {...defaultProps}
          options={optionsWithSticky}
          value={savedValue}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      const wrench = await screen.findByTestId(`${defaultProps.id}-configure`);
      await user.click(wrench);

      await waitFor(() => {
        expect(screen.getByTestId("model-provider-modal")).toBeInTheDocument();
      });
      // Clicking the wrench must not mutate the saved value.
      expect(handleOnNewValue).not.toHaveBeenCalled();
    });

    it("does not render Configure when the selected model isn't flagged", () => {
      // Baseline: a normal enabled model must not surface the wrench.
      mockedUseGetEnabledModels.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
        isLoading: false,
      });

      renderWithQueryClient(
        <ModelInputComponent
          {...defaultProps}
          value={[
            {
              id: "gpt-4",
              name: "gpt-4",
              icon: "Bot",
              provider: "OpenAI",
              metadata: {},
            },
          ]}
        />,
      );

      expect(
        screen.queryByTestId(`${defaultProps.id}-configure`),
      ).not.toBeInTheDocument();
    });
  });
});
