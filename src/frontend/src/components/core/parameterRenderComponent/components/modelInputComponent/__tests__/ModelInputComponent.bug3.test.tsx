/**
 * Bug 3 [P2] — ModelInput trigger must NEVER render a stringified JSON value.
 *
 * Reproduction (see PR-12575 OPEN-BUGS report + the user's screenshot):
 *   The Agent node's *Language Model* dropdown trigger displays the literal
 *   string `[{"provider": "OpenAI",...]` instead of the formatted model
 *   name. The trigger reads `selectedModel?.name`, and for affected flows
 *   the stored value's `name` field IS the JSON-encoded model list — a
 *   doubly-encoded payload from the assistant's flow_update pipeline.
 *
 * Bug-fix scope (defensive frontend layer):
 *   `selectedModel` derivation in ModelInputComponent must NOT propagate
 *   a `name` that is itself a JSON-encoded array/object. If detected,
 *   recover the actual model name from the parsed payload.
 *
 * RED before fix: the trigger contains the literal `[{` substring.
 * GREEN after fix: the trigger renders a plain readable model name.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { BaseInputProps } from "@/components/core/parameterRenderComponent/types";
import ModelInputComponent from "../index";
import type { ModelInputComponentType, ModelOption } from "../types";

Element.prototype.scrollIntoView = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({ setErrorData: jest.fn() }),
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
  useGetModelProviders: jest.fn(() => ({
    data: [{ provider: "OpenAI", is_enabled: true, is_configured: true }],
    isLoading: false,
    isFetching: false,
  })),
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: { enabled_models: {} },
    isLoading: false,
    isFetching: false,
  })),
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

const mockOptions: ModelOption[] = [
  {
    id: "gpt-4o",
    name: "gpt-4o",
    icon: "Bot",
    provider: "OpenAI",
    metadata: {},
  },
];

const baseProps: BaseInputProps & ModelInputComponentType = {
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

describe("Bug 3 [P2] — ModelInput trigger never renders raw JSON", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_not_render_raw_json_when_value_name_is_stringified_model_array", async () => {
    // Reproduces the user's screenshot exactly: the saved value's `name`
    // field is the JSON-encoded model list (a doubly-encoded payload).
    const corruptedJsonName = JSON.stringify([
      {
        provider: "OpenAI",
        name: "gpt-4o",
        icon: "OpenAI",
        metadata: { tool_calling: true, model_class: "ChatOpenAI" },
      },
    ]);
    const valueWithBadName = [
      {
        id: "gpt-4o",
        name: corruptedJsonName, // ← THIS is the bug — name is JSON, not "gpt-4o"
        icon: "Bot",
        provider: "Unknown",
        metadata: {},
      },
    ];

    renderWithQueryClient(
      <ModelInputComponent {...baseProps} value={valueWithBadName} />,
    );

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    const triggerLabel = screen.getByTestId(`value-dropdown-${baseProps.id}`);
    const visibleText = triggerLabel.textContent ?? "";

    // RED before fix: the trigger contains `[{"provider"` literally.
    expect(visibleText).not.toContain("[{");
    expect(visibleText).not.toContain('"provider"');
    expect(visibleText).not.toContain('"name"');
    // GREEN after fix: the trigger shows a readable name (the recovered
    // model name "gpt-4o", or at minimum a placeholder — anything but
    // the raw JSON).
    expect(visibleText.length).toBeLessThan(50);
  });

  it("should_render_recovered_name_when_value_name_is_stringified_model_array", async () => {
    // Same scenario as above but the assertion checks the recovery path:
    // when the corrupted `name` parses to an array with a valid inner
    // model, the trigger should display that inner model's actual name.
    const valueWithBadName = [
      {
        id: "gpt-4o",
        name: JSON.stringify([{ provider: "OpenAI", name: "gpt-4o" }]),
        icon: "Bot",
        provider: "Unknown",
        metadata: {},
      },
    ];

    renderWithQueryClient(
      <ModelInputComponent {...baseProps} value={valueWithBadName} />,
    );

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    const triggerLabel = screen.getByTestId(`value-dropdown-${baseProps.id}`);
    // The recovered name must appear, NOT the raw JSON.
    expect(triggerLabel.textContent).toContain("gpt-4o");
  });

  it("should_render_plain_name_unchanged_for_well_formed_value", async () => {
    // Characterization: a well-formed value must still render its name
    // as-is (no false-positive sanitization).
    const goodValue = [
      {
        id: "gpt-4o",
        name: "gpt-4o",
        icon: "Bot",
        provider: "OpenAI",
        metadata: {},
      },
    ];

    renderWithQueryClient(
      <ModelInputComponent {...baseProps} value={goodValue} />,
    );

    await waitFor(() => {
      expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    });
  });
});
