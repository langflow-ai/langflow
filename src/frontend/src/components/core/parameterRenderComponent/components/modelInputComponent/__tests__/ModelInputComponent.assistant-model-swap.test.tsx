/**
 * Silent model fallback on Assistant-driven model swap.
 *
 * Reproduction (QA run 52d182a7, item 1463 "Edit an existing flow via
 * Assistant"): the user asks the Assistant to set a specific non-default
 * model (e.g. "claude-sonnet-4-5-20250929", a VALID Anthropic registry
 * model). The Assistant applies that value via a `flow_update`/`configure`
 * event, but the persisted/displayed model silently falls back to a
 * different model. The Assistant reports success with the requested model
 * while the flow ends up on another — silent data loss + trust issue.
 *
 * Root cause exercised here: ModelInputComponent treats the
 * Assistant-applied value as "stale" when its name is not in the field's
 * `options`/enabled list but its provider IS configured locally. The
 * stale-reset `useEffect` then overwrites the value with `flatOptions[0]`.
 *
 * Source-of-truth note: the requested model exists in the model providers
 * list (registry), so it must be preserved — the providers list, not the
 * Agent's first enabled option, is the source of truth for valid models.
 *
 * RED before fix: `handleOnNewValue` is called to overwrite the
 * Assistant-applied model with a different one.
 * GREEN after fix: the Assistant-applied registry model is preserved.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

const REQUESTED_MODEL = "claude-sonnet-4-5-20250929";
const DEFAULT_MODEL = "claude-opus-4-6";

// The model field already carries the Agent's default Anthropic option
// (mirrors what's saved when the Agent picks its default). The Assistant
// then applies a DIFFERENT, valid registry model via flow_update.
const fieldOptions: ModelOption[] = [
  {
    id: DEFAULT_MODEL,
    name: DEFAULT_MODEL,
    icon: "Anthropic",
    provider: "Anthropic",
    metadata: { tool_calling: true },
  },
];

const assistantAppliedValue: ModelOption[] = [
  {
    name: REQUESTED_MODEL,
    icon: "Anthropic",
    provider: "Anthropic",
    metadata: { tool_calling: true },
  },
];

const baseProps: BaseInputProps & ModelInputComponentType = {
  id: "test-model-input",
  value: assistantAppliedValue,
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: fieldOptions,
  placeholder: "Setup Provider",
  nodeId: "agent-node",
  nodeClass: {
    template: {
      model: {
        model_type: "language",
        type: "model",
        required: false,
        list: false,
        show: true,
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

describe("Assistant-driven model swap — applied model must not fall back", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Anthropic IS configured locally and the registry (providers list,
    // the source of truth) exposes the requested model.
    (useGetModelProviders as jest.Mock).mockReturnValue({
      data: [
        {
          provider: "Anthropic",
          is_enabled: true,
          is_configured: true,
          icon: "Anthropic",
          models: [
            {
              model_name: DEFAULT_MODEL,
              metadata: { model_type: "language", tool_calling: true },
            },
            {
              model_name: REQUESTED_MODEL,
              metadata: { model_type: "language", tool_calling: true },
            },
          ],
        },
      ],
      isLoading: false,
      isFetching: false,
    });
    // The user has only enabled the default model — the freshly requested
    // model is a valid registry model that is not (yet) in enabled_models.
    (useGetEnabledModels as jest.Mock).mockReturnValue({
      data: { enabled_models: { Anthropic: { [DEFAULT_MODEL]: true } } },
      isLoading: false,
      isFetching: false,
    });
  });

  it("should_preserve_assistant_applied_model_when_provider_configured", async () => {
    const handleOnNewValue = jest.fn();
    renderWithQueryClient(
      <ModelInputComponent
        {...baseProps}
        value={assistantAppliedValue}
        handleOnNewValue={handleOnNewValue}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    // The component must NOT silently rewrite the Assistant's selection to
    // a different model. RED: the stale-reset useEffect calls
    // handleOnNewValue([{ name: DEFAULT_MODEL }]).
    const overwroteToDifferentModel = handleOnNewValue.mock.calls.some(
      (call) => {
        const next = call?.[0]?.value?.[0]?.name;
        return typeof next === "string" && next !== REQUESTED_MODEL;
      },
    );
    expect(overwroteToDifferentModel).toBe(false);
  });

  it("should_display_assistant_applied_model_in_trigger", async () => {
    renderWithQueryClient(
      <ModelInputComponent {...baseProps} value={assistantAppliedValue} />,
    );

    const trigger = await screen.findByTestId(`value-dropdown-${baseProps.id}`);
    expect(trigger.textContent).toContain(REQUESTED_MODEL);
  });
});
