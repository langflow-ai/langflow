import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { StepReview } from "../StepReview";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

const makeFile = (name: string) =>
  new File(["content"], name, { type: "text/plain" });

const makePreview = (content: string, idx = 0) => ({
  content,
  index: idx,
  metadata: { source: "test.txt", start: 0, end: content.length },
});

const baseProps = {
  files: [],
  chunkPreviews: [],
  isGeneratingPreview: false,
  currentChunkIndex: 0,
  onCurrentChunkIndexChange: jest.fn(),
  selectedPreviewFileIndex: 0,
  onSelectedPreviewFileIndexChange: jest.fn(),
  sourceName: "MyKnowledgeBase",
  totalFileSize: "1.2 KB",
  chunkSize: 512,
  chunkOverlap: 50,
  separator: "\\n",
  selectedEmbeddingModel: [],
};

beforeEach(() => jest.clearAllMocks());

describe("StepReview", () => {
  describe("Empty / loading / error states", () => {
    it('shows "No files selected" when files array is empty', () => {
      render(<StepReview {...baseProps} files={[]} />);
      expect(
        screen.getByText("No files selected. Go back to add files."),
      ).toBeInTheDocument();
    });

    it('shows "Generating preview..." spinner when isGeneratingPreview=true', () => {
      render(
        <StepReview
          {...baseProps}
          files={[makeFile("doc.txt")]}
          isGeneratingPreview
        />,
      );
      expect(screen.getByText("Generating preview...")).toBeInTheDocument();
    });

    it("shows error message when files exist, not generating, but no previews", () => {
      render(
        <StepReview
          {...baseProps}
          files={[makeFile("doc.txt")]}
          isGeneratingPreview={false}
          chunkPreviews={[]}
        />,
      );
      expect(
        screen.getByText(
          "Could not generate preview. Try adjusting your settings.",
        ),
      ).toBeInTheDocument();
    });

    it("renders chunk preview card when chunkPreviews are present", () => {
      render(
        <StepReview
          {...baseProps}
          files={[makeFile("doc.txt")]}
          chunkPreviews={[makePreview("Hello from chunk")]}
        />,
      );
      expect(screen.getByText("Hello from chunk")).toBeInTheDocument();
    });
  });

  describe("Summary section", () => {
    const propsWithFile = {
      ...baseProps,
      files: [makeFile("notes.txt"), makeFile("report.pdf")],
      chunkPreviews: [makePreview("some content")],
    };

    it("shows source name in the summary", () => {
      render(<StepReview {...propsWithFile} sourceName="ProjectDocs" />);
      expect(screen.getByText("ProjectDocs")).toBeInTheDocument();
    });

    it("shows file count in the summary", () => {
      render(<StepReview {...propsWithFile} />);
      expect(screen.getByText(/2 files/)).toBeInTheDocument();
    });

    it("shows total file size in the summary", () => {
      render(<StepReview {...propsWithFile} totalFileSize="3.5 KB" />);
      expect(screen.getByText(/3\.5 KB/)).toBeInTheDocument();
    });

    it("shows chunk size in the summary", () => {
      render(<StepReview {...propsWithFile} chunkSize={256} />);
      expect(screen.getByText("256 chars")).toBeInTheDocument();
    });

    it("shows chunk overlap in the summary", () => {
      render(<StepReview {...propsWithFile} chunkOverlap={25} />);
      expect(screen.getByText("25 chars")).toBeInTheDocument();
    });

    it("shows separator value in the summary", () => {
      render(<StepReview {...propsWithFile} separator="---" />);
      expect(screen.getByText("---")).toBeInTheDocument();
    });

    it('shows "None" when separator is empty', () => {
      render(<StepReview {...propsWithFile} separator="" />);
      expect(screen.getByText("None")).toBeInTheDocument();
    });

    it("shows embedding model name when model is selected", () => {
      render(
        <StepReview
          {...propsWithFile}
          selectedEmbeddingModel={[
            {
              id: "text-embedding-3-small",
              name: "text-embedding-3-small",
              provider: "OpenAI",
              icon: "OpenAI",
            },
          ]}
        />,
      );
      expect(screen.getByText("text-embedding-3-small")).toBeInTheDocument();
    });

    it('shows "Not selected" when no embedding model is selected', () => {
      render(<StepReview {...propsWithFile} selectedEmbeddingModel={[]} />);
      expect(screen.getByText("Not selected")).toBeInTheDocument();
    });
  });

  describe("Chunk navigation", () => {
    const previews = [
      makePreview("Chunk A"),
      makePreview("Chunk B"),
      makePreview("Chunk C"),
    ];
    const navProps = {
      ...baseProps,
      files: [makeFile("doc.txt")],
      chunkPreviews: previews,
      currentChunkIndex: 1,
    };

    it("calls onCurrentChunkIndexChange with index-1 when Prev is clicked", async () => {
      const onChangeIndex = jest.fn();
      const user = userEvent.setup();
      render(
        <StepReview
          {...navProps}
          currentChunkIndex={1}
          onCurrentChunkIndexChange={onChangeIndex}
        />,
      );
      const [prevBtn] = screen.getAllByRole("button");
      await user.click(prevBtn);
      expect(onChangeIndex).toHaveBeenCalledWith(0);
    });

    it("calls onCurrentChunkIndexChange with index+1 when Next is clicked", async () => {
      const onChangeIndex = jest.fn();
      const user = userEvent.setup();
      render(
        <StepReview
          {...navProps}
          currentChunkIndex={1}
          onCurrentChunkIndexChange={onChangeIndex}
        />,
      );
      const buttons = screen.getAllByRole("button");
      await user.click(buttons[buttons.length - 1]);
      expect(onChangeIndex).toHaveBeenCalledWith(2);
    });

    it("Prev button is disabled at first chunk (index 0)", () => {
      render(<StepReview {...navProps} currentChunkIndex={0} />);
      const [prevBtn] = screen.getAllByRole("button");
      expect(prevBtn).toBeDisabled();
    });

    it("Next button is disabled at last chunk", () => {
      render(<StepReview {...navProps} currentChunkIndex={2} />);
      const buttons = screen.getAllByRole("button");
      expect(buttons[buttons.length - 1]).toBeDisabled();
    });
  });

  describe("Multi-file dropdown", () => {
    it("shows a file picker dropdown when more than one file is uploaded", () => {
      render(
        <StepReview
          {...baseProps}
          files={[makeFile("a.txt"), makeFile("b.txt")]}
          chunkPreviews={[makePreview("content")]}
        />,
      );
      expect(screen.getByText("a.txt")).toBeInTheDocument();
    });

    it("does not show file picker when only one file is uploaded", () => {
      render(
        <StepReview
          {...baseProps}
          files={[makeFile("single.txt")]}
          chunkPreviews={[makePreview("content")]}
        />,
      );
      expect(screen.queryByText("b.txt")).not.toBeInTheDocument();
    });
  });
});
