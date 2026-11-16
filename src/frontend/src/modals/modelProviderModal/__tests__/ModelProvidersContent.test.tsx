import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ProviderVariable } from "@/constants/providerConstants";
import type { ModelTypeFilter } from "@/types/models";
import ModelProvidersContent from "../components/ModelProvidersContent";
import type { Provider } from "../components/types";

let mockProviders: Provider[];

const mockProviderVariables: ProviderVariable[] = [
  {
    variable_name: "Project ID",
    variable_key: "PROJECT_ID",
    required: true,
    is_secret: false,
    is_list: false,
    options: [],
  },
];

// The global icon mock supplies only the default export; ProviderListItem
// uses the named export as well.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({
    data: mockProviders,
    isLoading: false,
    isFetching: false,
    fetchStatus: "idle",
    isError: false,
  }),
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: () => ({
    data: { enabled_models: {} },
    isSuccess: true,
    isFetching: false,
    isFetchedAfterMount: true,
    fetchStatus: "idle",
    isError: false,
    refetch: jest.fn(),
  }),
}));

jest.mock("../hooks/useProviderConfiguration", () => ({
  useProviderConfiguration: ({
    selectedProvider,
  }: {
    selectedProvider: Provider | null;
  }) => {
    const { useState } = jest.requireActual<typeof import("react")>("react");
    const [variableValues, setVariableValues] = useState<
      Record<string, string>
    >({});

    return {
      variableValues,
      providerVariables: mockProviderVariables,
      syncedSelectedProvider: selectedProvider && {
        ...selectedProvider,
        ...mockProviders.find(
          (provider) => provider.provider === selectedProvider.provider,
        ),
      },
      handleVariableChange: (key: string, value: string) =>
        setVariableValues((previous) => ({ ...previous, [key]: value })),
      handleSaveAllVariables: jest.fn(),
      handleActivateProvider: jest.fn(),
      handleDisconnect: jest.fn(),
      handleModelToggle: jest.fn(),
      flushPendingChanges: jest.fn(),
      hasUserMadeChanges: jest.fn(),
      isVariableConfigured: () => false,
      getConfiguredValue: () => null,
      validationFailed: false,
      isSaving: false,
      isPending: false,
      isDeleting: false,
      isFetchingAfterSave: false,
      isFetchingAfterDisconnect: false,
      validationState: "idle",
      validationError: null,
      canSave: false,
      requiresConfiguration: true,
    };
  },
}));

const content = (modelType: ModelTypeFilter = "all") => (
  <TooltipProvider>
    <ModelProvidersContent modelType={modelType} />
  </TooltipProvider>
);

describe("ModelProvidersContent scrolling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Element.prototype.scrollIntoView = jest.fn();
    mockProviders = [
      {
        provider: "OpenAI",
        is_enabled: true,
        models: [{ model_name: "gpt-4", metadata: { model_type: "llm" } }],
      },
      {
        provider: "Anthropic",
        is_enabled: true,
        models: [{ model_name: "claude-3", metadata: { model_type: "llm" } }],
      },
    ];
  });

  it.each<ModelTypeFilter>(["all", "llm"])(
    "should scroll the selected provider panel to the top in the %s view",
    async (modelType) => {
      const user = userEvent.setup();
      render(content(modelType));
      await user.click(screen.getByTestId("provider-item-OpenAI"));
      screen.getByTestId("provider-content-scroll").scrollTop = 420;

      await user.click(screen.getByTestId("provider-item-Anthropic"));

      expect(screen.getByTestId("provider-item-Anthropic")).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      expect(screen.getByTestId("provider-content-scroll").scrollTop).toBe(0);
    },
  );

  it("should preserve the provider list scroll position when switching providers", async () => {
    const user = userEvent.setup();
    render(content());
    await user.click(screen.getByTestId("provider-item-OpenAI"));
    const providerList = screen.getByTestId("provider-list-scroll");
    providerList.scrollTop = 120;

    await user.click(screen.getByTestId("provider-item-Anthropic"));

    expect(providerList.scrollTop).toBe(120);
  });

  it("should preserve the provider panel scroll position when searching providers", async () => {
    const user = userEvent.setup();
    render(content());
    await user.click(screen.getByTestId("provider-item-OpenAI"));
    screen.getByTestId("provider-content-scroll").scrollTop = 420;

    await user.type(screen.getByTestId("provider-search-input"), "OpenAI");

    expect(screen.getByTestId("provider-content-scroll").scrollTop).toBe(420);
  });

  it("should preserve the provider panel scroll position when editing configuration", async () => {
    const user = userEvent.setup();
    render(content());
    await user.click(screen.getByTestId("provider-item-OpenAI"));
    screen.getByTestId("provider-content-scroll").scrollTop = 420;

    await user.type(screen.getByLabelText(/Project ID/), "unsaved-project");

    expect(screen.getByLabelText(/Project ID/)).toHaveValue("unsaved-project");
    expect(screen.getByTestId("provider-content-scroll").scrollTop).toBe(420);
  });

  it("should preserve the provider panel scroll position when its catalog refreshes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(content());
    await user.click(screen.getByTestId("provider-item-OpenAI"));
    screen.getByTestId("provider-content-scroll").scrollTop = 420;
    mockProviders = mockProviders.map((provider) => ({
      ...provider,
      models: [
        ...(provider.models ?? []),
        { model_name: "new-model", metadata: { model_type: "llm" } },
      ],
    }));

    rerender(content());

    expect(screen.getByText("new-model")).toBeVisible();
    expect(screen.getByTestId("provider-content-scroll").scrollTop).toBe(420);
  });
});
