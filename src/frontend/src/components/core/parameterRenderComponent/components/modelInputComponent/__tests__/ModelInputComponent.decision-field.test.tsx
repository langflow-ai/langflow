import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BaseInputProps } from "@/components/core/parameterRenderComponent/types";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import type { APIClassType } from "@/types/api";
import ModelInputComponent from "../index";
import type { ModelInputComponentType, ModelOption } from "../types";

Element.prototype.scrollIntoView = jest.fn();

const mockModalProps = jest.fn();

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
  useRefreshModelInputs: () => ({ refreshAllModelInputs: jest.fn() }),
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

jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: (props: unknown) => {
    mockModalProps(props);
    return null;
  },
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

const decision = (name: string, provider: string): ModelOption => ({
  name,
  provider,
  icon: provider,
  metadata: { model_type: "decision" },
});

const JEV = decision("jev-latest", "TypeSafe");
// gpt-6-luna is both an OpenAI chat model and a decision model.
const LUNA = decision("gpt-6-luna", "OpenAI");
const PPLX = decision("pplx-decider-latest", "Perplexity");

/** Smart Router in Decision Model mode: its language field is hidden. */
const smartRouter = (decisionModelType: unknown = "decision"): APIClassType =>
  ({
    template: {
      model: { type: "model", model_type: "language", show: false },
      decision_model: {
        type: "model",
        model_type: decisionModelType,
        show: true,
      },
    },
    description: "",
    display_name: "Smart Router",
    documentation: "",
  }) as unknown as APIClassType;

const EXTERNAL_OPTIONS = {
  fields: { data: { node: { icon: "Bot" } as APIClassType } },
};

const props = (
  overrides: Partial<BaseInputProps & ModelInputComponentType> = {},
): BaseInputProps & ModelInputComponentType => ({
  id: "decision-model-input",
  value: [],
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: [JEV, LUNA, PPLX],
  nodeId: "router",
  nodeClass: smartRouter(),
  fieldName: "decision_model",
  editNode: false,
  ...overrides,
});

const renderPicker = (
  overrides: Partial<BaseInputProps & ModelInputComponentType> = {},
) =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <ModelInputComponent {...props(overrides)} />
    </QueryClientProvider>,
  );

beforeEach(() => {
  jest.clearAllMocks();
  (useGetModelProviders as jest.Mock).mockReturnValue({
    data: [
      {
        provider: "TypeSafe",
        is_enabled: true,
        is_configured: true,
        icon: "TypeSafe",
        models: [{ model_name: "jev-latest", metadata: JEV.metadata }],
      },
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
        icon: "OpenAI",
        models: [
          { model_name: "gpt-6-luna", metadata: { model_type: "llm" } },
          { model_name: "gpt-6-luna", metadata: LUNA.metadata },
        ],
      },
      {
        provider: "Perplexity",
        is_enabled: true,
        is_configured: true,
        icon: "Perplexity",
        models: [
          { model_name: "pplx-decider-latest", metadata: PPLX.metadata },
        ],
      },
    ],
    isLoading: false,
    isFetching: false,
  });
  (useGetEnabledModels as jest.Mock).mockReturnValue({
    data: {
      // The untyped map says yes to every name; decision fields must ignore it.
      enabled_models: {
        OpenAI: { "gpt-6-luna": true },
        Perplexity: { "pplx-decider-latest": true },
      },
      enabled_models_by_type: {
        TypeSafe: { decision: { "jev-latest": true } },
        OpenAI: { llm: { "gpt-6-luna": true }, decision: {} },
      },
    },
    isLoading: false,
    isFetching: false,
  });
});

describe("ModelInputComponent on a decision field (LE-3129)", () => {
  it("offers only enabled decision models of the field it renders", async () => {
    const user = userEvent.setup();
    renderPicker();

    await user.click(screen.getByRole("combobox"));

    expect(screen.getByTestId("TypeSafe-jev-latest-option")).toBeVisible();
    // Enabled as a chat model only, so not offered as a decision model.
    expect(
      screen.queryByTestId("OpenAI-gpt-6-luna-option"),
    ).not.toBeInTheDocument();
    // Enabled only in the untyped map.
    expect(
      screen.queryByTestId("Perplexity-pplx-decider-latest-option"),
    ).not.toBeInTheDocument();
  });

  it("leaves an empty decision field empty", () => {
    const handleOnNewValue = jest.fn();
    renderPicker({ handleOnNewValue });
    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it("keeps a saved decision model that is no longer offered", () => {
    const handleOnNewValue = jest.fn();
    renderPicker({ value: [LUNA], handleOnNewValue });
    expect(screen.getByText("gpt-6-luna")).toBeInTheDocument();
    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it("stores the picked model with its provider", async () => {
    const user = userEvent.setup();
    const handleOnNewValue = jest.fn();
    renderPicker({ handleOnNewValue });

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByTestId("TypeSafe-jev-latest-option"));

    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: [
        {
          name: "jev-latest",
          icon: "TypeSafe",
          provider: "TypeSafe",
          metadata: JEV.metadata,
        },
      ],
    });
  });

  it("never offers Connect other models", async () => {
    const user = userEvent.setup();
    renderPicker({ externalOptions: EXTERNAL_OPTIONS });

    await user.click(screen.getByRole("combobox"));

    expect(screen.getByTestId("manage-model-providers")).toBeInTheDocument();
    expect(
      screen.queryByTestId("connect-other-models"),
    ).not.toBeInTheDocument();
  });

  it("opens Model Providers for decision models", async () => {
    const user = userEvent.setup();
    renderPicker();

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByTestId("manage-model-providers"));

    expect(mockModalProps).toHaveBeenLastCalledWith(
      expect.objectContaining({ modelType: "decision" }),
    );
  });

  it("refuses a model kind it does not know instead of guessing one", () => {
    renderPicker({ nodeClass: smartRouter("rerank") });

    expect(
      screen.getByTestId("model-input-unsupported-kind"),
    ).toHaveTextContent("Unsupported model type");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});

describe("ModelInputComponent on the language field of the same node", () => {
  it("reads the language field's kind and keeps Connect other models", async () => {
    const user = userEvent.setup();
    const languageOption: ModelOption = {
      name: "gpt-6-luna",
      provider: "OpenAI",
      icon: "OpenAI",
      metadata: { model_type: "llm" },
    };
    renderPicker({
      fieldName: "model",
      options: [languageOption],
      externalOptions: EXTERNAL_OPTIONS,
    });

    await user.click(screen.getByRole("combobox"));

    expect(screen.getByTestId("OpenAI-gpt-6-luna-option")).toBeVisible();
    expect(screen.getByTestId("connect-other-models")).toBeInTheDocument();
  });
});
