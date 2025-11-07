import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import ProviderList from "../provider-list";

// Mock the API hooks
jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: jest.fn(),
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(),
}));

jest.mock("@/controllers/API/queries/models/use-get-default-model", () => ({
  useGetDefaultModel: jest.fn(),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: jest.fn(),
}));

// Mock child components
jest.mock("../provider-list-item", () => {
  return function MockProviderListItem({ provider }: any) {
    return <div data-testid={`provider-item-${provider.provider}`}>{provider.provider}</div>;
  };
});

jest.mock("../provider-models-dialog", () => {
  return function MockProviderModelsDialog() {
    return <div data-testid="provider-models-dialog">Provider Models Dialog</div>;
  };
});

jest.mock("@/modals/apiKeyModal", () => {
  return function MockApiKeyModal() {
    return <div data-testid="api-key-modal">API Key Modal</div>;
  };
});

jest.mock("../use-provider-actions", () => ({
  useProviderActions: jest.fn(() => ({
    handleBatchToggleModels: jest.fn(),
    handleSetDefaultModel: jest.fn(),
    handleClearDefaultModel: jest.fn(),
    handleEnableProvider: jest.fn(),
    handleDeleteProvider: jest.fn(),
  })),
}));

const {
  useGetModelProviders,
} = require("@/controllers/API/queries/models/use-get-model-providers");
const {
  useGetEnabledModels,
} = require("@/controllers/API/queries/models/use-get-enabled-models");
const {
  useGetDefaultModel,
} = require("@/controllers/API/queries/models/use-get-default-model");
const { useGetGlobalVariables } = require("@/controllers/API/queries/variables");

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("ProviderList", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Default mock implementations
    useGetEnabledModels.mockReturnValue({ data: undefined });
    useGetDefaultModel.mockReturnValue({ data: undefined });
    useGetGlobalVariables.mockReturnValue({ data: undefined });
  });

  it("renders loading state", () => {
    useGetModelProviders.mockReturnValue({
      data: [],
      isLoading: true,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });
    expect(screen.getByText("Loading providers...")).toBeInTheDocument();
  });

  it("renders enabled providers section title", () => {
    useGetModelProviders.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });
    expect(screen.getByText("Enabled")).toBeInTheDocument();
  });

  it("renders available providers section title", () => {
    useGetModelProviders.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="available" />, { wrapper: createTestWrapper() });
    expect(screen.getByText("Available")).toBeInTheDocument();
  });

  it("renders no providers message when list is empty", () => {
    useGetModelProviders.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });
    expect(screen.getByText("No enabled providers")).toBeInTheDocument();
  });

  it("filters and renders enabled providers", () => {
    useGetModelProviders.mockReturnValue({
      data: [
        {
          provider: "OpenAI",
          icon: "Bot",
          is_enabled: true,
          models: [{ model_name: "gpt-4", metadata: {} }],
        },
        {
          provider: "Anthropic",
          icon: "Bot",
          is_enabled: false,
          models: [{ model_name: "claude-3", metadata: {} }],
        },
      ],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });

    expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
    expect(screen.queryByTestId("provider-item-Anthropic")).not.toBeInTheDocument();
  });

  it("filters and renders available providers", () => {
    useGetModelProviders.mockReturnValue({
      data: [
        {
          provider: "OpenAI",
          icon: "Bot",
          is_enabled: true,
          models: [{ model_name: "gpt-4", metadata: {} }],
        },
        {
          provider: "Anthropic",
          icon: "Bot",
          is_enabled: false,
          models: [{ model_name: "claude-3", metadata: {} }],
        },
      ],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="available" />, { wrapper: createTestWrapper() });

    expect(screen.queryByTestId("provider-item-OpenAI")).not.toBeInTheDocument();
    expect(screen.getByTestId("provider-item-Anthropic")).toBeInTheDocument();
  });

  it("excludes providers with all deprecated and not supported models", () => {
    useGetModelProviders.mockReturnValue({
      data: [
        {
          provider: "OpenAI",
          icon: "Bot",
          is_enabled: true,
          models: [
            {
              model_name: "deprecated-model",
              metadata: { deprecated: true, not_supported: true },
            },
          ],
        },
      ],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });
    expect(screen.queryByTestId("provider-item-OpenAI")).not.toBeInTheDocument();
  });

  it("renders provider models dialog", () => {
    useGetModelProviders.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });
    expect(screen.getByTestId("provider-models-dialog")).toBeInTheDocument();
  });

  it("renders API key modal", () => {
    useGetModelProviders.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
    });

    render(<ProviderList type="enabled" />, { wrapper: createTestWrapper() });
    expect(screen.getByTestId("api-key-modal")).toBeInTheDocument();
  });
});
