import { fireEvent, render, screen } from "@testing-library/react";
import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
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
  labels: { nodes: { "Agent-1": "Agent" } },
});

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
      />,
    );

    expect(screen.getByText("Edited Model on Agent")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Show changes" }),
    ).not.toBeInTheDocument();
  });
});
