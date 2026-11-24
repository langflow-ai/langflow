import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
  name: "claude-sonnet-5",
  icon: "Anthropic",
  provider: "Anthropic",
  metadata: { model_type: "llm" },
};

const OPENAI_MODEL: ModelOption = {
  name: "gpt-4o-mini",
  icon: "OpenAI",
  provider: "OpenAI",
  metadata: { model_type: "llm" },
};

const baseProps: BaseInputProps & ModelInputComponentType = {
  id: "test-model-input",
  value: [SAVED_MODEL],
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: [OPENAI_MODEL],
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

const OPENAI_PROVIDER = {
  provider: "OpenAI",
  is_enabled: true,
  is_configured: true,
  icon: "OpenAI",
  models: [{ model_name: "gpt-4o-mini", metadata: { model_type: "llm" } }],
};

/**
 * An administrator hid the saved model after it was selected: the provider is
 * still configured, but the model is filtered out of both the catalog and the
 * enabled-models map (it is not reported as disabled — it is simply gone).
 */
const mockModelHiddenByPolicy = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [
      {
        provider: "Anthropic",
        is_enabled: false,
        is_configured: true,
        icon: "Anthropic",
        models: [],
      },
      OPENAI_PROVIDER,
    ],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: {
      enabled_models: { Anthropic: {}, OpenAI: { "gpt-4o-mini": true } },
    },
    isLoading: false,
    isFetching: false,
  });
};

/** The whole provider was revoked: it no longer appears in /models at all. */
const mockProviderRevoked = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [OPENAI_PROVIDER],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: { enabled_models: { OpenAI: { "gpt-4o-mini": true } } },
    isLoading: false,
    isFetching: false,
  });
};

/** Nothing is offered to this user at all (an Enterprise install that starts closed). */
const mockNoProvidersOffered = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: { enabled_models: {} },
    isLoading: false,
    isFetching: false,
  });
};

describe("ModelInputComponent — saved model restricted after selection (LE-1960)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it.each([
    ["the model was hidden by policy", mockModelHiddenByPolicy],
    ["the provider was revoked", mockProviderRevoked],
    ["no provider is offered at all", mockNoProvidersOffered],
  ])(
    "keeps naming the saved model, flags it as not available, and never swaps the value when %s",
    (_case, arrange) => {
      arrange();
      const handleOnNewValue = jest.fn();

      renderWithQueryClient(
        <ModelInputComponent
          {...baseProps}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      // The field still says which model it is set to — not "Select a model",
      // and not the first model of some other provider.
      expect(screen.getByText("claude-sonnet-5")).toBeInTheDocument();
      expect(screen.queryByText("gpt-4o-mini")).not.toBeInTheDocument();
      // ...and says why it cannot be used, aligned with the runtime error.
      const marker = screen.getByTestId(`${baseProps.id}-unavailable`);
      expect(marker).toHaveTextContent("Not available");
      expect(marker).toHaveAttribute(
        "title",
        expect.stringContaining("restricted by an administrator"),
      );
      // The configure wrench belongs to "not enabled locally", not to this,
      // and the setup-provider call to action must not replace the field.
      expect(
        screen.queryByTestId(`${baseProps.id}-configure`),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Setup Provider")).not.toBeInTheDocument();
      expect(screen.getByRole("combobox")).toBeInTheDocument();
      // The saved value is kept so lifting the restriction restores it.
      expect(handleOnNewValue).not.toHaveBeenCalled();
    },
  );

  it("does not flag a model that is still offered", () => {
    (useGetModelProviders as jest.Mock).mockReturnValue({
      data: [
        {
          provider: "Anthropic",
          is_enabled: true,
          is_configured: true,
          icon: "Anthropic",
          models: [
            { model_name: "claude-sonnet-5", metadata: { model_type: "llm" } },
          ],
        },
      ],
      isLoading: false,
      isFetching: false,
    });
    (useGetEnabledModels as jest.Mock).mockReturnValue({
      data: { enabled_models: { Anthropic: { "claude-sonnet-5": true } } },
      isLoading: false,
      isFetching: false,
    });

    renderWithQueryClient(
      <ModelInputComponent {...baseProps} options={[SAVED_MODEL]} />,
    );

    expect(screen.getByText("claude-sonnet-5")).toBeInTheDocument();
    expect(
      screen.queryByTestId(`${baseProps.id}-unavailable`),
    ).not.toBeInTheDocument();
  });
});
