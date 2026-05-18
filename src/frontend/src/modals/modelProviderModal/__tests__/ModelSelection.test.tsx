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

    it("should not bubble toggle clicks to parent containers", async () => {
      const onModelToggle = jest.fn();
      const onParentClick = jest.fn();
      const user = userEvent.setup();

      render(
        <div onClick={onParentClick}>
          <ModelSelection {...defaultProps} onModelToggle={onModelToggle} />
        </div>,
      );

      const toggle = screen.getByTestId(
        "embeddings-toggle-text-embedding-ada-002",
      );
      await user.click(toggle);

      expect(onModelToggle).toHaveBeenCalledWith(
        "text-embedding-ada-002",
        expect.any(Boolean),
      );
      expect(onParentClick).not.toHaveBeenCalled();
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

    it("should show empty state message for Ollama when no models are available", () => {
      render(
        <ModelSelection
          {...defaultProps}
          providerName="Ollama"
          availableModels={[]}
          isEnabledModel={true}
        />,
      );

      expect(screen.getByText("No models available")).toBeInTheDocument();
      expect(
        screen.getByText(
          /models installed for Ollama. Please pull the models you want to use./i,
        ),
      ).toBeInTheDocument();
      expect(screen.getByText("Check Ollama Library")).toBeInTheDocument();
    });
  });

  describe("Search filtering", () => {
    it("should render the search input when there are available models", () => {
      render(<ModelSelection {...defaultProps} />);
      expect(screen.getByTestId("model-search-input")).toBeInTheDocument();
    });

    it("should filter LLM and embedding lists by the typed query", async () => {
      const user = userEvent.setup();
      render(<ModelSelection {...defaultProps} />);

      await user.type(screen.getByTestId("model-search-input"), "embed");

      // gpt-4 / gpt-3.5-turbo are filtered out (no "embed" substring).
      expect(screen.queryByText("gpt-4")).not.toBeInTheDocument();
      expect(screen.queryByText("gpt-3.5-turbo")).not.toBeInTheDocument();
      expect(screen.getByText("text-embedding-ada-002")).toBeInTheDocument();
      expect(screen.getByText("embed-large")).toBeInTheDocument();
    });

    it("should render the no-match message when the query matches nothing", async () => {
      const user = userEvent.setup();
      render(<ModelSelection {...defaultProps} />);

      await user.type(screen.getByTestId("model-search-input"), "xyzzy");

      expect(screen.getByTestId("model-search-empty")).toBeInTheDocument();
      expect(
        screen.queryByTestId("llm-models-section"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("embeddings-models-section"),
      ).not.toBeInTheDocument();
    });

    it("should reset the query when the selected provider changes", async () => {
      const user = userEvent.setup();
      const { rerender } = render(<ModelSelection {...defaultProps} />);

      const input = screen.getByTestId(
        "model-search-input",
      ) as HTMLInputElement;
      await user.type(input, "gpt");
      expect(input.value).toBe("gpt");

      rerender(<ModelSelection {...defaultProps} providerName="Anthropic" />);

      const refreshed = screen.getByTestId(
        "model-search-input",
      ) as HTMLInputElement;
      expect(refreshed.value).toBe("");
    });

    it("should not render the search input when no models are available at all", () => {
      render(
        <ModelSelection
          {...defaultProps}
          providerName="Ollama"
          availableModels={[]}
          isEnabledModel={true}
        />,
      );
      expect(
        screen.queryByTestId("model-search-input"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Capability tags", () => {
    const tagModels: Model[] = [
      {
        model_name: "claude-opus",
        metadata: {
          model_type: "llm",
          icon: "Bot",
          tool_calling: true,
          reasoning: true,
          vision: true,
        },
      },
      {
        model_name: "vanilla-llm",
        metadata: { model_type: "llm", icon: "Bot", tool_calling: false },
      },
      {
        model_name: "embed-only",
        metadata: { model_type: "embeddings", icon: "Bot" },
      },
      {
        model_name: "preview-model",
        metadata: {
          model_type: "llm",
          icon: "Bot",
          preview: true,
          search: true,
        },
      },
    ];

    it("should render tags for the capabilities present in metadata", () => {
      render(
        <ModelSelection
          {...defaultProps}
          availableModels={tagModels}
          modelType="all"
        />,
      );

      expect(
        screen.getByTestId("llm-tag-tool-claude-opus"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("llm-tag-reasoning-claude-opus"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("llm-tag-vision-claude-opus"),
      ).toBeInTheDocument();

      expect(
        screen.getByTestId("llm-tag-preview-preview-model"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("llm-tag-search-preview-model"),
      ).toBeInTheDocument();

      // Embedding models surface the "embedding" tag only in the all-view
      // because the dedicated section heading already conveys the same info.
      expect(
        screen.getByTestId("embeddings-tag-embedding-embed-only"),
      ).toBeInTheDocument();
    });

    it("should not render absent capability tags", () => {
      render(
        <ModelSelection
          {...defaultProps}
          availableModels={tagModels}
          modelType="all"
        />,
      );

      expect(
        screen.queryByTestId("llm-tag-tool-vanilla-llm"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("llm-tag-reasoning-vanilla-llm"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("llm-tag-vision-vanilla-llm"),
      ).not.toBeInTheDocument();
    });

    it("should not render the embedding tag when modelType is embeddings", () => {
      render(
        <ModelSelection
          {...defaultProps}
          availableModels={tagModels}
          modelType="embeddings"
        />,
      );

      expect(
        screen.queryByTestId("embeddings-tag-embedding-embed-only"),
      ).not.toBeInTheDocument();
    });
  });
});
