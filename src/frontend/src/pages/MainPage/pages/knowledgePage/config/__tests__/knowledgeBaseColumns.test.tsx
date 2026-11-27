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
let mockUseLabelSeam = false;
jest.mock("@/customization/components/custom-resource-access-label", () => ({
  __esModule: true,
  default: (props: {
    resourceType: string;
    resourceId: string;
    isOwned: boolean;
  }) =>
    mockUseLabelSeam ? (
      <span
        data-testid="access-label"
        data-resource-type={props.resourceType}
        data-resource-id={props.resourceId}
        data-owned={String(props.isOwned)}
      >
        via Admin Role
      </span>
    ) : null,
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
import {
  createKnowledgeBaseColumns,
  isKnowledgeBaseOwned,
} from "../knowledgeBaseColumns";

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
  it("returns 7 column definitions", () => {
    const cols = createKnowledgeBaseColumns();
    expect(cols).toHaveLength(7);
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
        "Status",
        "Actions",
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

    it("exposes the full name when hovering a truncated name", () => {
      const name = "Quarterly customer research and support documentation";
      const nameCol = createKnowledgeBaseColumns().find(
        (column) => column.field === "name",
      )!;
      const CellRenderer =
        nameCol.cellRenderer as React.ComponentType<NameCellRendererProps>;
      render(<CellRenderer data={makeKb({ name })} value={name} />);

      expect(screen.getByTitle(name)).toHaveTextContent(name);
      expect(screen.getByTitle(name)).toHaveClass("truncate");
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
      return cols.find((c) => c.field === "actions")!
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
      return cols.find((c) => c.field === "actions")!
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

describe("knowledge base access label", () => {
  const renderNameCell = (kb: KnowledgeBaseInfo) => {
    const nameCol = createKnowledgeBaseColumns().find(
      (c) => c.field === "name",
    );
    const Renderer = nameCol?.cellRenderer as (
      p: NameCellRendererProps,
    ) => React.ReactElement;
    return render(<Renderer data={kb} value={kb.name} />);
  };

  afterEach(() => {
    mockUseLabelSeam = false;
  });

  it.each([
    [true, true],
    [false, false],
    [undefined, true],
    [null, true],
  ])("should_treat_is_owner_%p_as_owned_%p", (isOwner, expected) => {
    expect(isKnowledgeBaseOwned(makeKb({ is_owner: isOwner }))).toBe(expected);
  });

  it("should_leave_the_name_cell_unchanged_when_the_label_is_the_default", () => {
    const { container } = renderNameCell(makeKb({ is_owner: false }));

    const cell = container.firstElementChild as HTMLElement;
    expect(cell.children).toHaveLength(2);
    const name = cell.lastElementChild as HTMLElement;
    expect(name).toHaveTextContent("My KB");
    expect(name.children).toHaveLength(0);
  });

  it("should_render_the_label_inside_the_name_span_so_it_takes_its_own_line", () => {
    mockUseLabelSeam = true;
    const { container } = renderNameCell(
      makeKb({ id: "kb-42", name: "legal-kb", is_owner: false }),
    );

    const label = screen.getByTestId("access-label");
    const name = screen.getByTitle("legal-kb");
    // The name keeps the row's full width; the label is not a flex sibling.
    expect(container.firstElementChild?.children).toHaveLength(2);
    expect(name.lastElementChild).toBe(label);
    expect(name.firstChild?.textContent).toBe("legal-kb");
    expect(label).toHaveAttribute("data-resource-type", "knowledge_base");
    expect(label).toHaveAttribute("data-resource-id", "kb-42");
    expect(label).toHaveAttribute("data-owned", "false");
  });

  it("should_mark_an_older_backend_kb_without_is_owner_as_owned", () => {
    mockUseLabelSeam = true;
    renderNameCell(makeKb());

    expect(screen.getByTestId("access-label")).toHaveAttribute(
      "data-owned",
      "true",
    );
  });

  it("should_keep_a_long_unbroken_name_truncated_with_the_full_name_in_title", () => {
    mockUseLabelSeam = true;
    const longName = `kb_${"x".repeat(300)}`;
    renderNameCell(makeKb({ name: longName }));

    const name = screen.getByTitle(longName);
    expect(name).toHaveClass("truncate");
    expect(name.parentElement).toHaveClass("min-w-0");
  });
});

describe("knowledge base name column sizing", () => {
  it("should_reserve_room_for_a_one_line_access_label_when_the_grid_is_narrow", () => {
    const nameCol = createKnowledgeBaseColumns().find(
      (c) => c.field === "name",
    );

    // Rows are a fixed 45px, so the label under the name cannot wrap; 280px
    // fits "Shared by priya (Full access)" beside the checkbox and icon.
    expect(nameCol).toMatchObject({ flex: 2, minWidth: 280 });
  });
});
