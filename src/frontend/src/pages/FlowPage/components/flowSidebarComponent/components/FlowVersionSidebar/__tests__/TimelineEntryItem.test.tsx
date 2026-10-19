import { fireEvent, render, screen } from "@testing-library/react";
import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import { flowNames } from "@/utils/flow-operations/names";
import TimelineEntryItem from "../components/TimelineEntryItem";

jest.mock("@/components/ui/sidebar", () => ({
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => (
    <li>{children}</li>
  ),
  SidebarMenuButton: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <div role="menuitem" onClick={onClick}>
      {children}
    </div>
  ),
}));

const actor = { id: "u1", username: "Alice" };

const writes = (fields: string[], cause?: string): RecordedOperation => ({
  revision: 1,
  actor,
  request_id: "r",
  cause,
  operation: {
    type: "update_nodes",
    updates: fields.map((field) => ({
      op: "set_field",
      id: "Agent-1",
      path: ["data", "node", "template", field, "value"],
      value: 1,
    })),
  },
});

const describeOptions = {
  names: flowNames({
    nodes: [{ id: "Agent-1", data: { node: { display_name: "Agent" } } }],
  }),
};

const versionActions = {
  onExportVersion: jest.fn(),
  onDeleteVersion: jest.fn(),
};

const entry = (operations: RecordedOperation[]): RevisionEntry => ({
  id: "e1",
  start_revision: 1,
  end_revision: 1,
  created_at: null,
  actors: [actor],
  request_ids: ["r"],
  versions: [],
  operations,
});

describe("TimelineEntryItem", () => {
  it("folds an entry one action caused into one line, changes collapsed", () => {
    const onSelect = jest.fn();
    render(
      <TimelineEntryItem
        entry={entry([writes(["model", "temperature"], "upgrade_component")])}
        isSelected={false}
        onSelect={onSelect}
        describe={describeOptions}
        {...versionActions}
      />,
    );

    expect(
      screen.getByText("Alice updated Agent; 2 fields changed"),
    ).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Show changes" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/^Edited /)).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(
      screen.getByRole("button", { name: "Hide changes" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText("Edited Model, Temperature on Agent"),
    ).toBeInTheDocument();
    // Expanding the details does not select the entry.
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("shows an ordinary entry's changes without a toggle", () => {
    render(
      <TimelineEntryItem
        entry={entry([writes(["model"])])}
        isSelected={false}
        onSelect={jest.fn()}
        describe={describeOptions}
        {...versionActions}
      />,
    );

    expect(screen.getByText("Edited Model on Agent")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Show changes" }),
    ).not.toBeInTheDocument();
  });

  it("offers Export and Delete on a saved version it holds", () => {
    const onSelect = jest.fn();
    const onExportVersion = jest.fn();
    const onDeleteVersion = jest.fn();
    const version = {
      id: "v1",
      version_number: 1,
      version_tag: "v1",
      description: "Before the demo",
      created_at: "2026-01-01T00:00:00Z",
      operation_revision: 1,
      saved_by: actor,
    };
    render(
      <TimelineEntryItem
        entry={{ ...entry([writes(["model"])]), versions: [version] }}
        isSelected={false}
        onSelect={onSelect}
        describe={describeOptions}
        onExportVersion={onExportVersion}
        onDeleteVersion={onDeleteVersion}
      />,
    );

    expect(screen.getByText("Before the demo")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "Export" }));
    expect(onExportVersion).toHaveBeenCalledWith(version);
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    expect(onDeleteVersion).toHaveBeenCalledWith(version);
    // The version's menu does not select the entry.
    expect(onSelect).not.toHaveBeenCalled();
  });
});
