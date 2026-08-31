import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
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

const ANTHROPIC_MODEL: ModelOption = {
  name: "claude-opus-5",
  icon: "Anthropic",
  provider: "Anthropic",
  metadata: { model_type: "llm" },
};

const OPENAI_MODEL: ModelOption = {
  name: "gpt-5.6-sol",
  icon: "OpenAI",
  provider: "OpenAI",
  metadata: { model_type: "llm" },
};

const baseProps: BaseInputProps & ModelInputComponentType = {
  id: "test-model-input",
  value: [],
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: [ANTHROPIC_MODEL],
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

const mockAnthropicConnected = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [
      {
        provider: "Anthropic",
        is_enabled: true,
        is_configured: true,
        icon: "Anthropic",
        models: [
          { model_name: "claude-opus-5", metadata: { model_type: "llm" } },
        ],
      },
    ],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: { enabled_models: { Anthropic: { "claude-opus-5": true } } },
    isLoading: false,
    isFetching: false,
  });
};

const mockAnthropicDisconnectedOpenAiConnected = () => {
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [
      {
        provider: "Anthropic",
        is_enabled: false,
        is_configured: false,
        models: [
          { model_name: "claude-opus-5", metadata: { model_type: "llm" } },
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

describe("ModelInputComponent — revalidation after an auto-select", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_replace_a_selected_model_once_its_provider_is_disconnected", async () => {
    mockAnthropicConnected();
    const handleOnNewValue = jest.fn();

    // Selection is given up front: an empty field is no longer auto-filled (LE-2168).
    const { rerender } = renderWithQueryClient(
      <ModelInputComponent
        {...baseProps}
        value={[ANTHROPIC_MODEL]}
        handleOnNewValue={handleOnNewValue}
      />,
    );

    expect(handleOnNewValue).not.toHaveBeenCalled();
    mockAnthropicDisconnectedOpenAiConnected();

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    rerender(
      <QueryClientProvider client={queryClient}>
        <ModelInputComponent
          {...baseProps}
          value={[ANTHROPIC_MODEL]}
          options={[ANTHROPIC_MODEL, OPENAI_MODEL]}
          handleOnNewValue={handleOnNewValue}
        />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(handleOnNewValue).toHaveBeenCalled();
    });
    expect(handleOnNewValue.mock.calls[0][0].value[0].name).toBe("gpt-5.6-sol");
  });
});
