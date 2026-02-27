import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelSelection from "../components/ModelSelection";
import { Model } from "../components/types";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Mock enabled models hook
const mockEnabledModels = {
  enabled_models: {
    OpenAI: {
      "gpt-4": true,
      "gpt-3.5-turbo": false,
    },
  },
};

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: mockEnabledModels,
    isLoading: false,
  })),
}));

const mockLLMModels: Model[] = [
  { model_name: "gpt-4", metadata: { model_type: "llm", icon: "Bot" } },
  { model_name: "gpt-3.5-turbo", metadata: { model_type: "llm", icon: "Bot" } },
];

const mockEmbeddingModels: Model[] = [
  {
    model_name: "text-embedding-ada-002",
    metadata: { model_type: "embeddings", icon: "Bot" },
  },
  {
    model_name: "embed-large",
    metadata: { model_type: "embeddings", icon: "Bot" },
  },
];

const allModels = [...mockLLMModels, ...mockEmbeddingModels];

describe("ModelSelection", () => {
  const defaultProps = {
    availableModels: allModels,
    onModelToggle: jest.fn(),
    modelType: "all" as const,
    providerName: "OpenAI",
    isEnabledModel: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render the component container", () => {
      render(<ModelSelection {...defaultProps} />);

      expect(
        screen.getByTestId("model-provider-selection"),
      ).toBeInTheDocument();
    });

    it("should render LLM section when modelType is all", () => {
      render(<ModelSelection {...defaultProps} />);

      expect(screen.getByTestId("llm-models-section")).toBeInTheDocument();
      expect(screen.getByText("Language Models")).toBeInTheDocument();
    });

    it("should render Embeddings section when modelType is all", () => {
      render(<ModelSelection {...defaultProps} />);

      expect(
        screen.getByTestId("embeddings-models-section"),
      ).toBeInTheDocument();
      expect(screen.getByText("Embedding Models")).toBeInTheDocument();
    });

    it("should only render LLM section when modelType is llm", () => {
      render(<ModelSelection {...defaultProps} modelType="llm" />);

      expect(screen.getByTestId("llm-models-section")).toBeInTheDocument();
      expect(
        screen.queryByTestId("embeddings-models-section"),
      ).not.toBeInTheDocument();
    });

    it("should only render Embeddings section when modelType is embeddings", () => {
      render(<ModelSelection {...defaultProps} modelType="embeddings" />);

      expect(
        screen.queryByTestId("llm-models-section"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByTestId("embeddings-models-section"),
      ).toBeInTheDocument();
    });
  });

  describe("Model Display", () => {
    it("should render model names", () => {
      render(<ModelSelection {...defaultProps} />);

      expect(screen.getByText("gpt-4")).toBeInTheDocument();
      expect(screen.getByText("gpt-3.5-turbo")).toBeInTheDocument();
      expect(screen.getByText("text-embedding-ada-002")).toBeInTheDocument();
      expect(screen.getByText("embed-large")).toBeInTheDocument();
    });

    it("should render toggle switches when isEnabledModel is true", () => {
      render(<ModelSelection {...defaultProps} />);

      expect(screen.getByTestId("llm-toggle-gpt-4")).toBeInTheDocument();
      expect(
        screen.getByTestId("llm-toggle-gpt-3.5-turbo"),
      ).toBeInTheDocument();
    });

    it("should not render toggle switches when isEnabledModel is false", () => {
      render(<ModelSelection {...defaultProps} isEnabledModel={false} />);

      expect(screen.queryByTestId("llm-toggle-gpt-4")).not.toBeInTheDocument();
    });
  });

  describe("Toggle Interaction", () => {
    it("should call onModelToggle when toggle is clicked", async () => {
      const onModelToggle = jest.fn();
      const user = userEvent.setup();

      render(
        <ModelSelection {...defaultProps} onModelToggle={onModelToggle} />,
      );

      const toggle = screen.getByTestId("llm-toggle-gpt-4");
      await user.click(toggle);

      expect(onModelToggle).toHaveBeenCalledWith("gpt-4", expect.any(Boolean));
    });
  });

  describe("Empty States", () => {
    it("should not render LLM section when no LLM models", () => {
      render(
        <ModelSelection
          {...defaultProps}
          availableModels={mockEmbeddingModels}
        />,
      );

      expect(
        screen.queryByTestId("llm-models-section"),
      ).not.toBeInTheDocument();
    });

    it("should not render Embeddings section when no embedding models", () => {
      render(
        <ModelSelection {...defaultProps} availableModels={mockLLMModels} />,
      );

      expect(
        screen.queryByTestId("embeddings-models-section"),
      ).not.toBeInTheDocument();
    });
  });
});
