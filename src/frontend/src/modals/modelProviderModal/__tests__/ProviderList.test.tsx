import { render, screen } from "@testing-library/react";
import ProviderList from "../components/ProviderList";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name: string;
    className?: string;
  }) => (
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

// Mock provider data
const mockProviders = [
  {
    provider: "OpenAI",
    icon: "Bot",
    is_enabled: true,
    models: [
      { model_name: "gpt-4", metadata: { model_type: "llm" } },
      { model_name: "gpt-3.5-turbo", metadata: { model_type: "llm" } },
      {
        model_name: "text-embedding-ada-002",
        metadata: { model_type: "embeddings" },
      },
    ],
  },
  {
    provider: "Anthropic",
    icon: "Brain",
    is_enabled: false,
    models: [{ model_name: "claude-3", metadata: { model_type: "llm" } }],
  },
];

let mockIsLoading = false;
let mockIsFetching = false;

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: jest.fn(() => ({
    data: mockProviders,
    isLoading: mockIsLoading,
    isFetching: mockIsFetching,
  })),
}));

interface MockProviderListItemProps {
  provider: { provider: string; model_count?: number };
  isSelected: boolean;
  onSelect: (provider: MockProviderListItemProps["provider"]) => void;
}

// Mock ProviderListItem
jest.mock("../components/ProviderListItem", () => ({
  __esModule: true,
  default: ({ provider, isSelected, onSelect }: MockProviderListItemProps) => (
    <button
      type="button"
      data-testid={`provider-item-${provider.provider}`}
      data-selected={isSelected}
      onClick={() => onSelect(provider)}
    >
      {provider.provider} - {provider.model_count} models
    </button>
  ),
}));

describe("ProviderList", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockIsLoading = false;
    mockIsFetching = false;
  });

  describe("Loading State", () => {
    it("should show loading state when isLoading is true", () => {
      mockIsLoading = true;

      // Re-import to get fresh mock
      const useGetModelProvidersMock =
        require("@/controllers/API/queries/models/use-get-model-providers").useGetModelProviders;
      useGetModelProvidersMock.mockReturnValueOnce({
        data: [],
        isLoading: true,
        isFetching: false,
      });

      render(<ProviderList modelType="all" />);

      expect(screen.getByTestId("provider-list-loading")).toBeInTheDocument();
      expect(screen.getByText("Loading providers")).toBeInTheDocument();
    });

    it("does not render stale provider cards during a scoped refetch", () => {
      const useGetModelProvidersMock =
        require("@/controllers/API/queries/models/use-get-model-providers").useGetModelProviders;
      useGetModelProvidersMock.mockReturnValueOnce({
        data: mockProviders,
        isLoading: false,
        isFetching: true,
        isError: false,
      });

      render(<ProviderList modelType="all" flowId="flow-a" />);

      expect(screen.getByTestId("provider-list-loading")).toBeInTheDocument();
      expect(screen.queryByTestId("provider-list")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("provider-item-OpenAI"),
      ).not.toBeInTheDocument();
    });

    it("does not render stale provider cards while a scoped refetch is paused", () => {
      const useGetModelProvidersMock =
        require("@/controllers/API/queries/models/use-get-model-providers").useGetModelProviders;
      useGetModelProvidersMock.mockReturnValueOnce({
        data: mockProviders,
        isLoading: false,
        isFetching: false,
        fetchStatus: "paused",
        isError: false,
      });

      render(<ProviderList modelType="all" flowId="flow-a" />);

      expect(screen.getByTestId("provider-list-loading")).toBeInTheDocument();
      expect(screen.queryByTestId("provider-list")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("provider-item-OpenAI"),
      ).not.toBeInTheDocument();
    });

    it("does not render stale provider cards after a scoped refetch error", () => {
      const useGetModelProvidersMock =
        require("@/controllers/API/queries/models/use-get-model-providers").useGetModelProviders;
      useGetModelProvidersMock.mockReturnValueOnce({
        data: mockProviders,
        isLoading: false,
        isFetching: false,
        isError: true,
        error: new Error("scope refresh denied"),
      });

      render(<ProviderList modelType="all" flowId="flow-a" />);

      expect(screen.getByTestId("provider-list-error")).toBeInTheDocument();
      expect(screen.queryByTestId("provider-list")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("provider-item-OpenAI"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Provider Display", () => {
    it("requests only providers configurable in the active scope", () => {
      const useGetModelProvidersMock =
        require("@/controllers/API/queries/models/use-get-model-providers").useGetModelProviders;

      render(
        <ProviderList
          modelType="all"
          flowId="flow-one"
          projectId="project-one"
        />,
      );

      expect(useGetModelProvidersMock).toHaveBeenCalledWith({
        includeDeprecated: true,
        flowId: "flow-one",
        projectId: "project-one",
        purpose: "configure",
      });
    });

    it("should render provider list container", () => {
      render(<ProviderList modelType="all" />);

      expect(screen.getByTestId("provider-list")).toBeInTheDocument();
    });

    it("should render providers with all model types", () => {
      render(<ProviderList modelType="all" />);

      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
      expect(screen.getByTestId("provider-item-Anthropic")).toBeInTheDocument();
    });

    it("should filter providers by LLM model type", () => {
      render(<ProviderList modelType="llm" />);

      // Both providers have LLM models
      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
      expect(screen.getByTestId("provider-item-Anthropic")).toBeInTheDocument();
    });

    it("should filter providers by embeddings model type", () => {
      render(<ProviderList modelType="embeddings" />);

      // OpenAI has embedding models
      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
      // Anthropic has no embedding models but still renders (shows "no models" alert)
      expect(screen.getByTestId("provider-item-Anthropic")).toBeInTheDocument();
    });
  });

  describe("Selection", () => {
    it("should call onProviderSelect when provider is clicked", () => {
      const onProviderSelect = jest.fn();

      render(
        <ProviderList modelType="all" onProviderSelect={onProviderSelect} />,
      );

      screen.getByTestId("provider-item-OpenAI").click();

      expect(onProviderSelect).toHaveBeenCalled();
    });

    it("should pass selectedProviderName to items", () => {
      render(<ProviderList modelType="all" selectedProviderName="OpenAI" />);

      const openaiItem = screen.getByTestId("provider-item-OpenAI");
      expect(openaiItem).toHaveAttribute("data-selected", "true");

      const anthropicItem = screen.getByTestId("provider-item-Anthropic");
      expect(anthropicItem).toHaveAttribute("data-selected", "false");
    });
  });

  describe("Search filtering", () => {
    it("should render every provider when the query is empty", () => {
      render(<ProviderList modelType="all" query="" />);

      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
      expect(screen.getByTestId("provider-item-Anthropic")).toBeInTheDocument();
    });

    it("should filter providers by case-insensitive substring match", () => {
      render(<ProviderList modelType="all" query="ANTHROP" />);

      expect(
        screen.queryByTestId("provider-item-OpenAI"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("provider-item-Anthropic")).toBeInTheDocument();
    });

    it("should show the no-results message when nothing matches", () => {
      render(<ProviderList modelType="all" query="xyzzy" />);

      expect(screen.queryByTestId("provider-list")).not.toBeInTheDocument();
      expect(screen.getByTestId("provider-list-empty")).toBeInTheDocument();
    });

    it("should ignore leading and trailing whitespace in the query", () => {
      render(<ProviderList modelType="all" query="  open  " />);

      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
      expect(
        screen.queryByTestId("provider-item-Anthropic"),
      ).not.toBeInTheDocument();
    });
  });
});
