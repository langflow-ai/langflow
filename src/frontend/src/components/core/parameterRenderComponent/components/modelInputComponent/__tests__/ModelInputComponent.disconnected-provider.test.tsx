import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BaseInputProps } from "@/components/core/parameterRenderComponent/types";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import ModelInputComponent from "../index";
import type { ModelInputComponentType, ModelOption } from "../types";

Element.prototype.scrollIntoView = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({ setErrorData: jest.fn() }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "flow-one" }),
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: jest.fn(),
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
  useTypesStore: { getState: () => ({ data: {} }) },
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: jest.fn(),
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: jest.fn(() => ({ mutateAsync: jest.fn() })),
}));

jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: jest.fn(),
}));

jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/common/loadingTextComponent", () => ({
  __esModule: true,
  default: ({ text }: { text: string }) => (
    <span data-testid="loading-text">{text}</span>
  ),
}));

const SAVED_MODEL: ModelOption = {
  name: "claude-opus-5",
  icon: "Anthropic",
  provider: "Anthropic",
  metadata: { model_type: "llm" },
};

const STICKY_SAVED_MODEL: ModelOption = {
  ...SAVED_MODEL,
  metadata: { ...SAVED_MODEL.metadata, not_enabled_locally: true },
};

const OPENAI_MODEL: ModelOption = {
  name: "gpt-5.6-sol",
  icon: "OpenAI",
  provider: "OpenAI",
  metadata: { model_type: "llm" },
};
const baseProps: BaseInputProps & ModelInputComponentType = {
  id: "test-model-input",
  value: [SAVED_MODEL],
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: [SAVED_MODEL],
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

/**
 * Post-disconnect backend shape: the provider stays in the catalog with
 * `is_configured: false`, and `/enabled_models` reports every one of its
 * models as `false` (see `get_enabled_models`, which ANDs on provider_status).
 */
const mockDisconnectedProvider = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [
      {
        provider: "Anthropic",
        is_enabled: false,
        is_configured: false,
        models: [
          {
            model_name: "claude-opus-5",
            metadata: { model_type: "llm" },
          },
        ],
      },
    ],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: { enabled_models: { Anthropic: { "claude-opus-5": false } } },
    isLoading: false,
    isFetching: false,
  });
};

/** The user reconnects a different provider while the saved one stays disconnected. */
const mockConnectedOpenAiAndDisconnectedAnthropic = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [
      {
        provider: "Anthropic",
        is_enabled: false,
        is_configured: false,
        models: [
          {
            model_name: "claude-opus-5",
            metadata: { model_type: "llm" },
          },
        ],
      },
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
        icon: "OpenAI",
        models: [
          { model_name: "gpt-5.6-sol", metadata: { model_type: "llm" } },
        ],
      },
    ],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: {
      enabled_models: {
        Anthropic: { "claude-opus-5": false },
        OpenAI: { "gpt-5.6-sol": true },
      },
    },
    isLoading: false,
    isFetching: false,
  });
};

describe("ModelInputComponent — provider disconnected after a model was saved", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDisconnectedProvider();
  });

  it("should_show_setup_provider_state_when_the_saved_model_provider_is_disconnected", () => {
    renderWithQueryClient(<ModelInputComponent {...baseProps} />);

    expect(screen.getByText("Setup Provider")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("should_list_connected_models_but_not_the_sticky_saved_model_from_a_disconnected_provider", async () => {
    mockConnectedOpenAiAndDisconnectedAnthropic();
    const user = userEvent.setup();
    renderWithQueryClient(
      <ModelInputComponent
        {...baseProps}
        options={[OPENAI_MODEL, STICKY_SAVED_MODEL]}
      />,
    );

    await user.click(screen.getByRole("combobox"));

    expect(
      await screen.findByTestId("OpenAI-gpt-5.6-sol-option"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("Anthropic-claude-opus-5-option"),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["absent", undefined],
    [
      "stale",
      {
        enabled_models: {
          Anthropic: { "claude-opus-5": true },
          OpenAI: { "gpt-5.6-sol": true },
        },
      },
    ],
  ])(
    "should_hide_an_untagged_model_from_a_known_disconnected_provider_when_enabled_model_data_is_%s",
    async (_state, enabledModelsData) => {
      mockConnectedOpenAiAndDisconnectedAnthropic();
      (useGetEnabledModels as jest.Mock).mockReturnValue({
        data: enabledModelsData,
        isLoading: false,
        isFetching: false,
      });
      const user = userEvent.setup();

      renderWithQueryClient(
        <ModelInputComponent
          {...baseProps}
          value={[OPENAI_MODEL]}
          options={[OPENAI_MODEL, SAVED_MODEL]}
        />,
      );

      await user.click(screen.getByRole("combobox"));

      expect(
        await screen.findByTestId("OpenAI-gpt-5.6-sol-option"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("Anthropic-claude-opus-5-option"),
      ).not.toBeInTheDocument();
    },
  );
  it("should_not_render_the_configure_wrench_next_to_the_setup_provider_button", () => {
    renderWithQueryClient(<ModelInputComponent {...baseProps} />);

    expect(
      screen.queryByTestId(`${baseProps.id}-configure`),
    ).not.toBeInTheDocument();
  });

  it("should_switch_to_a_valid_model_when_another_provider_gets_connected", async () => {
    mockConnectedOpenAiAndDisconnectedAnthropic();

    const handleOnNewValue = jest.fn();
    renderWithQueryClient(
      <ModelInputComponent
        {...baseProps}
        handleOnNewValue={handleOnNewValue}
      />,
    );

    await waitFor(() => {
      expect(handleOnNewValue).toHaveBeenCalled();
    });
    expect(handleOnNewValue.mock.calls[0][0].value[0].name).toBe("gpt-5.6-sol");
  });

  it("should_drop_the_configure_wrench_once_the_valid_model_is_applied", () => {
    mockConnectedOpenAiAndDisconnectedAnthropic();

    renderWithQueryClient(
      <ModelInputComponent
        {...baseProps}
        value={[
          {
            name: "gpt-5.6-sol",
            icon: "OpenAI",
            provider: "OpenAI",
            metadata: {},
          },
        ]}
      />,
    );

    expect(screen.getByText("gpt-5.6-sol")).toBeInTheDocument();
    expect(
      screen.queryByTestId(`${baseProps.id}-configure`),
    ).not.toBeInTheDocument();
  });

  it("should_keep_the_saved_value_untouched_so_reconnecting_restores_it", () => {
    const handleOnNewValue = jest.fn();
    renderWithQueryClient(
      <ModelInputComponent
        {...baseProps}
        handleOnNewValue={handleOnNewValue}
      />,
    );

    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it.each([
    {
      state: "provider refetch in flight",
      providerFetching: true,
    },
    {
      state: "provider refetch failed with stale data",
      providerError: new Error("provider refetch failed"),
    },
    {
      state: "enabled-model refetch in flight",
      enabledFetching: true,
    },
    {
      state: "enabled-model refetch failed with stale data",
      enabledError: new Error("enabled-model refetch failed"),
    },
  ])(
    "should_not_replace_the_saved_model_while_$state",
    ({
      providerFetching = false,
      providerError,
      enabledFetching = false,
      enabledError,
    }) => {
      mockConnectedOpenAiAndDisconnectedAnthropic();
      const providerQuery = (useGetModelProviders as jest.Mock)();
      const enabledQuery = (useGetEnabledModels as jest.Mock)();
      (useGetModelProviders as jest.Mock).mockReturnValue({
        ...providerQuery,
        isFetching: providerFetching,
        error: providerError,
      });
      (useGetEnabledModels as jest.Mock).mockReturnValue({
        ...enabledQuery,
        isFetching: enabledFetching,
        error: enabledError,
      });
      const handleOnNewValue = jest.fn();

      renderWithQueryClient(
        <ModelInputComponent
          {...baseProps}
          options={[OPENAI_MODEL, STICKY_SAVED_MODEL]}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
      if (providerFetching || enabledFetching) {
        expect(screen.getByText("Loading models")).toBeInTheDocument();
      } else {
        expect(
          screen.getByTestId("model-input-load-failed"),
        ).toBeInTheDocument();
      }
      expect(handleOnNewValue).not.toHaveBeenCalled();
    },
  );
});
