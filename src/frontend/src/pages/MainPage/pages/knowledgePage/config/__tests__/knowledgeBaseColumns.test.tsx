import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));
jest.mock("@/components/common/loadingTextComponent", () => ({
  __esModule: true,
  default: ({ text }: { text: string }) => <span>{text}</span>,
}));
jest.mock("@/utils/stringManipulation", () => ({
  formatFileSize: (v: number) => `${v} B`,
}));
jest.mock("@/utils/styleUtils", () => ({
  FILE_ICONS: {
    pdf: {
      icon: "FileText",
      color: "text-datatype-red dark:text-datatype-red-foreground",
    },
    txt: {
      icon: "FileCode",
      color: "text-datatype-purple dark:text-datatype-purple-foreground",
    },
  },
}));

import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { createKnowledgeBaseColumns } from "../knowledgeBaseColumns";

const makeKb = (
  overrides: Partial<KnowledgeBaseInfo> = {},
): KnowledgeBaseInfo => ({
  id: "kb-1",
  dir_name: "my_kb",
  name: "My KB",
  embedding_provider: "OpenAI",
  embedding_model: "text-embedding-3-small",
  size: 1024,
  words: 200,
  characters: 1200,
  chunks: 15,
  avg_chunk_size: 80,
  status: "ready",
  source_types: [],
  ...overrides,
});

type NameCellRendererProps = {
  data: KnowledgeBaseInfo;
  value: string;
};

type StatusCellRendererProps = {
  data: KnowledgeBaseInfo;
};

describe("createKnowledgeBaseColumns", () => {
  it("returns 8 column definitions", () => {
    const cols = createKnowledgeBaseColumns();
    expect(cols).toHaveLength(8);
  });

  it("includes the expected header names", () => {
    const headers = createKnowledgeBaseColumns().map((c) => c.headerName);
    expect(headers).toEqual(
      expect.arrayContaining([
        "Name",
        "Size",
        "Embedding Model",
        "Vector Store",
        "Chunks",
        "Avg Chunk Size",
        "Status",
      ]),
    );
  });

  describe("Name cell renderer", () => {
    it("renders the KB name", () => {
      const cols = createKnowledgeBaseColumns();
      const nameCol = cols.find((c) => c.headerName === "Name")!;
      const CellRenderer =
        nameCol.cellRenderer as React.ComponentType<NameCellRendererProps>;
      render(<CellRenderer data={makeKb()} value="My KB" />);
      expect(screen.getByText("My KB")).toBeInTheDocument();
    });

    it("shows a file icon when source_types is empty", () => {
      const cols = createKnowledgeBaseColumns();
      const nameCol = cols.find((c) => c.headerName === "Name")!;
      const CellRenderer =
        nameCol.cellRenderer as React.ComponentType<NameCellRendererProps>;
      render(
        <CellRenderer data={makeKb({ source_types: [] })} value="My KB" />,
      );
      expect(screen.getByTestId("icon-File")).toBeInTheDocument();
    });

    it("shows Layers icon when multiple source types present", () => {
      const cols = createKnowledgeBaseColumns();
      const nameCol = cols.find((c) => c.headerName === "Name")!;
      const CellRenderer =
        nameCol.cellRenderer as React.ComponentType<NameCellRendererProps>;
      render(
        <CellRenderer
          data={makeKb({ source_types: ["pdf", "txt"] })}
          value="My KB"
        />,
      );
      expect(screen.getByTestId("icon-Layers")).toBeInTheDocument();
    });
  });

  describe("Status cell renderer", () => {
    const getStatusRenderer = () => {
      const cols = createKnowledgeBaseColumns();
      return cols.find((c) => c.headerName === "Status")!
        .cellRenderer as React.ComponentType<StatusCellRendererProps>;
    };

    it('renders "Ready" label for ready status', () => {
      const CellRenderer = getStatusRenderer();
      render(<CellRenderer data={makeKb({ status: "ready" })} />);
      expect(screen.getByText("Ready")).toBeInTheDocument();
    });

    it('renders "Failed" label for failed status', () => {
      const CellRenderer = getStatusRenderer();
      render(<CellRenderer data={makeKb({ status: "failed" })} />);
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });

    it('renders "Ingesting" label for ingesting status', () => {
      const CellRenderer = getStatusRenderer();
      render(<CellRenderer data={makeKb({ status: "ingesting" })} />);
      expect(screen.getByText("Ingesting")).toBeInTheDocument();
    });

    it('renders "Empty" label for empty status', () => {
      const CellRenderer = getStatusRenderer();
      render(<CellRenderer data={makeKb({ status: "empty" })} />);
      expect(screen.getByText("Empty")).toBeInTheDocument();
    });
  });

  describe("Actions cell renderer callbacks", () => {
    const getActionsRenderer = (callbacks = {}) => {
      const cols = createKnowledgeBaseColumns(callbacks);
      return cols.find((c) => c.headerName === "")!
        .cellRenderer as React.ComponentType<StatusCellRendererProps>;
    };

    it("calls onDelete when Delete menu item is clicked for a ready KB", async () => {
      const onDelete = jest.fn();
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({ onDelete });
      render(<CellRenderer data={makeKb({ status: "ready" })} />);

      await user.click(screen.getByTestId("kb-row-actions-trigger"));
      await user.click(screen.getByText("Delete"));
      expect(onDelete).toHaveBeenCalledWith(
        expect.objectContaining({ dir_name: "my_kb" }),
      );
    });

    it("calls onAddSources when Ingest Files is clicked for a ready KB", async () => {
      const onAddSources = jest.fn();
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({ onAddSources });
      render(<CellRenderer data={makeKb({ status: "ready" })} />);

      await user.click(screen.getByTestId("kb-row-actions-trigger"));
      await user.click(screen.getByText("Ingest Files"));
      expect(onAddSources).toHaveBeenCalledWith(
        expect.objectContaining({ dir_name: "my_kb" }),
      );
    });

    it("calls onViewChunks when View Chunks is clicked", async () => {
      const onViewChunks = jest.fn();
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({ onViewChunks });
      render(<CellRenderer data={makeKb({ status: "ready" })} />);

      await user.click(screen.getByTestId("kb-row-actions-trigger"));
      await user.click(screen.getByText("View Chunks"));
      expect(onViewChunks).toHaveBeenCalledWith(
        expect.objectContaining({ dir_name: "my_kb" }),
      );
    });

    it("shows Stop Ingestion instead of Delete for an ingesting KB", async () => {
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({});
      render(<CellRenderer data={makeKb({ status: "ingesting" })} />);

      await user.click(screen.getByTestId("kb-row-actions-trigger"));
      expect(screen.getByText("Stop Ingestion")).toBeInTheDocument();
      expect(screen.queryByText("Delete")).not.toBeInTheDocument();
    });

    it("calls onStopIngestion when Stop Ingestion is clicked", async () => {
      const onStopIngestion = jest.fn();
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({ onStopIngestion });
      render(<CellRenderer data={makeKb({ status: "ingesting" })} />);

      await user.click(screen.getByTestId("kb-row-actions-trigger"));
      await user.click(screen.getByText("Stop Ingestion"));
      expect(onStopIngestion).toHaveBeenCalledWith(
        expect.objectContaining({ dir_name: "my_kb" }),
      );
    });

    it("disables Ingest Files for an ingesting KB", async () => {
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({});
      render(<CellRenderer data={makeKb({ status: "ingesting" })} />);

      await user.click(screen.getByTestId("kb-row-actions-trigger"));
      const updateItem = screen
        .getByText("Ingest Files")
        .closest('[role="menuitem"]');
      expect(updateItem).toHaveAttribute("data-disabled");
    });
  });

  describe("Row ingest files icon shortcut", () => {
    const getActionsRenderer = (callbacks = {}) => {
      const cols = createKnowledgeBaseColumns(callbacks);
      return cols.find((c) => c.headerName === "")!
        .cellRenderer as React.ComponentType<StatusCellRendererProps>;
    };

    it("renders the ingest files icon button on each row", () => {
      const CellRenderer = getActionsRenderer({});
      render(<CellRenderer data={makeKb({ status: "ready" })} />);
      expect(screen.getByTestId("kb-row-update-button")).toBeInTheDocument();
    });

    it("calls onAddSources directly when ingest files icon is clicked", async () => {
      const onAddSources = jest.fn();
      const user = userEvent.setup();
      const CellRenderer = getActionsRenderer({ onAddSources });
      render(<CellRenderer data={makeKb({ status: "ready" })} />);

      await user.click(screen.getByTestId("kb-row-update-button"));
      expect(onAddSources).toHaveBeenCalledWith(
        expect.objectContaining({ dir_name: "my_kb" }),
      );
    });

    it("disables the ingest files icon button while KB is ingesting", () => {
      const CellRenderer = getActionsRenderer({});
      render(<CellRenderer data={makeKb({ status: "ingesting" })} />);
      expect(screen.getByTestId("kb-row-update-button")).toBeDisabled();
    });
  });
});
