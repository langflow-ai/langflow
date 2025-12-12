import { render, screen } from "@testing-library/react";
import ModelProviderActive from "../components/ModelProviderActive";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

describe("ModelProviderActive", () => {
  describe("Rendering", () => {
    it("should render the component container", () => {
      render(<ModelProviderActive activeLLMs={[]} activeEmbeddings={[]} />);

      expect(screen.getByTestId("model-provider-active")).toBeInTheDocument();
      expect(screen.getByText("Models")).toBeInTheDocument();
    });

    it("should render LLM badges when activeLLMs is provided", () => {
      const activeLLMs = ["gpt-4", "gpt-3.5-turbo"];

      render(
        <ModelProviderActive activeLLMs={activeLLMs} activeEmbeddings={[]} />,
      );

      expect(screen.getByText("LLM")).toBeInTheDocument();
      expect(screen.getByTestId("active-llm-badge-gpt-4")).toBeInTheDocument();
      expect(
        screen.getByTestId("active-llm-badge-gpt-3.5-turbo"),
      ).toBeInTheDocument();
      expect(screen.getByText("gpt-4")).toBeInTheDocument();
      expect(screen.getByText("gpt-3.5-turbo")).toBeInTheDocument();
    });

    it("should render embedding badges when activeEmbeddings is provided", () => {
      const activeEmbeddings = ["text-embedding-ada-002", "embed-large"];

      render(
        <ModelProviderActive
          activeLLMs={[]}
          activeEmbeddings={activeEmbeddings}
        />,
      );

      expect(screen.getByText("Embeddings")).toBeInTheDocument();
      expect(
        screen.getByTestId("active-embedding-badge-text-embedding-ada-002"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("active-embedding-badge-embed-large"),
      ).toBeInTheDocument();
    });

    it("should render both LLM and embedding sections when both are provided", () => {
      const activeLLMs = ["gpt-4"];
      const activeEmbeddings = ["text-embedding-ada-002"];

      render(
        <ModelProviderActive
          activeLLMs={activeLLMs}
          activeEmbeddings={activeEmbeddings}
        />,
      );

      expect(screen.getByText("LLM")).toBeInTheDocument();
      expect(screen.getByText("Embeddings")).toBeInTheDocument();
      expect(screen.getByTestId("active-llm-badge-gpt-4")).toBeInTheDocument();
      expect(
        screen.getByTestId("active-embedding-badge-text-embedding-ada-002"),
      ).toBeInTheDocument();
    });

    it("should not render LLM section when activeLLMs is empty", () => {
      render(
        <ModelProviderActive activeLLMs={[]} activeEmbeddings={["embed"]} />,
      );

      expect(screen.queryByText("LLM")).not.toBeInTheDocument();
      expect(screen.getByText("Embeddings")).toBeInTheDocument();
    });

    it("should not render Embeddings section when activeEmbeddings is empty", () => {
      render(
        <ModelProviderActive activeLLMs={["gpt-4"]} activeEmbeddings={[]} />,
      );

      expect(screen.getByText("LLM")).toBeInTheDocument();
      expect(screen.queryByText("Embeddings")).not.toBeInTheDocument();
    });

    it("should render info icon", () => {
      render(<ModelProviderActive activeLLMs={[]} activeEmbeddings={[]} />);

      expect(screen.getByTestId("icon-info")).toBeInTheDocument();
    });
  });

  describe("Multiple Models", () => {
    it("should render multiple LLM badges", () => {
      const activeLLMs = ["model-1", "model-2", "model-3"];

      render(
        <ModelProviderActive activeLLMs={activeLLMs} activeEmbeddings={[]} />,
      );

      activeLLMs.forEach((model) => {
        expect(
          screen.getByTestId(`active-llm-badge-${model}`),
        ).toBeInTheDocument();
      });
    });

    it("should render multiple embedding badges", () => {
      const activeEmbeddings = ["embed-1", "embed-2", "embed-3"];

      render(
        <ModelProviderActive
          activeLLMs={[]}
          activeEmbeddings={activeEmbeddings}
        />,
      );

      activeEmbeddings.forEach((model) => {
        expect(
          screen.getByTestId(`active-embedding-badge-${model}`),
        ).toBeInTheDocument();
      });
    });
  });
});
