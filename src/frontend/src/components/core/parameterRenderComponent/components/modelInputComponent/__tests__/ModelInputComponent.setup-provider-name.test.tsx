import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BaseInputProps } from "@/components/core/parameterRenderComponent/types";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import ModelInputComponent from "../index";
import type { ModelInputComponentType } from "../types";

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
  default: () => <div data-testid="provider-modal" />,
}));

// Rendered without a text child on purpose: the real component renders an
// <svg>, which contributes nothing to an accessible name computed from
// content. A mock that prints the icon name would hide exactly the bug under
// test by padding the name with text the user never sees.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className} />
  ),
}));

jest.mock("@/components/common/loadingTextComponent", () => ({
  __esModule: true,
  default: ({ text }: { text: string }) => (
    <span data-testid="loading-text">{text}</span>
  ),
}));

const baseProps: BaseInputProps & ModelInputComponentType = {
  id: "test-model-input",
  value: [],
  disabled: false,
  handleOnNewValue: jest.fn(),
  options: [],
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

/** No provider configured at all — the trigger collapses to the CTA button. */
const mockNoProvidersConfigured = () => {
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

/**
 * WCAG 2.5.3 (Label in Name): the setup-provider branch of the trigger is a
 * plain button whose visible text *is* its label, not a value. Forwarding the
 * field label as the sole accessible name dropped "Setup Provider" from it
 * entirely — screen reader users heard the field name instead of the action,
 * and speech-input users saying "click Setup Provider" hit nothing.
 */
describe("ModelInputComponent — Setup Provider accessible name", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNoProvidersConfigured();
  });

  it("keeps the visible button text in the accessible name when a field label is forwarded", () => {
    renderWithQueryClient(
      <>
        <span id="model-field-label">Language Model required</span>
        <ModelInputComponent
          {...baseProps}
          ariaLabelledBy="model-field-label"
        />
      </>,
    );

    const button = screen.getByRole("button", { name: /Setup Provider/i });
    // The field label still supplies context, so the two controls the field
    // can render (this CTA and the configured-state combobox) stay
    // distinguishable by name.
    expect(button).toHaveAccessibleName(
      "Setup Provider Language Model required",
    );
  });

  it("leads the accessible name with the visible text so speech input can target it", () => {
    renderWithQueryClient(
      <>
        <span id="model-field-label">Language Model required</span>
        <ModelInputComponent
          {...baseProps}
          ariaLabelledBy="model-field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("button", { name: /Setup Provider/i }),
    ).toHaveAccessibleName(/^Setup Provider/);
  });

  it("keeps the visible button text when only a literal aria-label is forwarded", () => {
    renderWithQueryClient(
      <ModelInputComponent {...baseProps} aria-label="Embedding model" />,
    );

    expect(
      screen.getByRole("button", { name: /Setup Provider/i }),
    ).toHaveAccessibleName("Setup Provider, Embedding model");
  });

  it("names the button from its own content when no field label is forwarded", () => {
    renderWithQueryClient(<ModelInputComponent {...baseProps} />);

    expect(
      screen.getByRole("button", { name: /Setup Provider/i }),
    ).toHaveAccessibleName("Setup Provider");
  });

  it("still opens the provider manager when activated by its accessible name", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <>
        <span id="model-field-label">Language Model required</span>
        <ModelInputComponent
          {...baseProps}
          ariaLabelledBy="model-field-label"
        />
      </>,
    );

    await user.click(screen.getByRole("button", { name: /Setup Provider/i }));

    expect(await screen.findByTestId("provider-modal")).toBeInTheDocument();
  });
});
