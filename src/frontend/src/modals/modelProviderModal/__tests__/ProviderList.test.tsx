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

// Mock ProviderListItem
jest.mock("../components/ProviderListItem", () => ({
  __esModule: true,
  default: ({ provider, isSelected, onSelect }: any) => (
    <div
      data-testid={`provider-item-${provider.provider}`}
      data-selected={isSelected}
      onClick={() => onSelect(provider)}
    >
      {provider.provider} - {provider.model_count} models
    </div>
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
  });

  describe("Provider Display", () => {
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

      // Only OpenAI has embedding models
      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
      expect(
        screen.queryByTestId("provider-item-Anthropic"),
      ).not.toBeInTheDocument();
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
});
