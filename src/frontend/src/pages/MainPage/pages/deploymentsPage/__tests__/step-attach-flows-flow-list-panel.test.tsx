import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowType } from "@/types/flow";
import type { ConnectionItem } from "../types";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import { FlowListPanel } from "../components/step-attach-flows-flow-list-panel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFlow(overrides: Partial<FlowType> & { id: string }): FlowType {
  return {
    name: `Flow ${overrides.id}`,
    data: null,
    description: "",
    ...overrides,
  } as FlowType;
}

const flows: FlowType[] = [
  makeFlow({ id: "f1", name: "Alpha Flow" }),
  makeFlow({ id: "f2", name: "Beta Flow" }),
  makeFlow({ id: "f3", name: "Gamma Flow" }),
];

const connections: ConnectionItem[] = [
  {
    id: "conn-1",
    connectionId: "cid-1",
    name: "Prod Connection",
    variableCount: 0,
    isNew: false,
    environmentVariables: {},
  },
  {
    id: "conn-2",
    connectionId: "cid-2",
    name: "Dev Connection",
    variableCount: 0,
    isNew: false,
    environmentVariables: {},
  },
];

const defaultProps = {
  flows,
  selectedFlowId: null as string | null,
  selectedVersionByFlow: new Map<
    string,
    { versionId: string; versionTag: string }
  >(),
  attachedConnectionByFlow: new Map<string, string[]>(),
  connections,
  removedFlowIds: new Set<string>(),
  onSelectFlow: jest.fn(),
  onRemoveFlow: jest.fn(),
  onUndoRemoveFlow: jest.fn(),
};

function renderPanel(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(<FlowListPanel {...props} />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Rendering flow items
// ---------------------------------------------------------------------------

describe("Rendering flow items", () => {
  it("renders all flow items", () => {
    renderPanel();
    expect(screen.getByText("Alpha Flow")).toBeInTheDocument();
    expect(screen.getByText("Beta Flow")).toBeInTheDocument();
    expect(screen.getByText("Gamma Flow")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ATTACHED badge
// ---------------------------------------------------------------------------

describe("ATTACHED badge", () => {
  it("shows ATTACHED badge for flows in selectedVersionByFlow map", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    renderPanel({ selectedVersionByFlow });
    expect(screen.getByText("ATTACHED")).toBeInTheDocument();
  });

  it("does not show ATTACHED badge for flows not in the map", () => {
    renderPanel();
    expect(screen.queryByText("ATTACHED")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// REMOVED badge and opacity
// ---------------------------------------------------------------------------

describe("REMOVED badge and opacity", () => {
  it("shows REMOVED badge for flows in removedFlowIds set", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    const removedFlowIds = new Set(["f1"]);
    renderPanel({ selectedVersionByFlow, removedFlowIds });
    expect(screen.getByText("REMOVED")).toBeInTheDocument();
    // ATTACHED should not show for removed flows
    expect(screen.queryByText("ATTACHED")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Version labels
// ---------------------------------------------------------------------------

describe("Version labels", () => {
  it("shows version label when attached and not removed", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    renderPanel({ selectedVersionByFlow });
    expect(screen.getByText("v1.0")).toBeInTheDocument();
  });

  it("does not show version label for removed flows", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    const removedFlowIds = new Set(["f1"]);
    renderPanel({ selectedVersionByFlow, removedFlowIds });
    expect(screen.queryByText("v1.0")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Connection name mapping
// ---------------------------------------------------------------------------

describe("Connection names", () => {
  it("correctly maps connection IDs to names using connections array", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    const attachedConnectionByFlow = new Map([["f1", ["conn-1", "conn-2"]]]);
    renderPanel({ selectedVersionByFlow, attachedConnectionByFlow });
    expect(
      screen.getByText("Prod Connection, Dev Connection"),
    ).toBeInTheDocument();
  });

  it("does not show connection names for removed flows", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    const attachedConnectionByFlow = new Map([["f1", ["conn-1"]]]);
    const removedFlowIds = new Set(["f1"]);
    renderPanel({
      selectedVersionByFlow,
      attachedConnectionByFlow,
      removedFlowIds,
    });
    expect(screen.queryByText("Prod Connection")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Remove button
// ---------------------------------------------------------------------------

describe("Remove button", () => {
  it("triggers onRemoveFlow callback when clicking the detach button", async () => {
    const user = userEvent.setup();
    const onRemoveFlow = jest.fn();
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    renderPanel({ selectedVersionByFlow, onRemoveFlow });

    await user.click(screen.getByTestId("detach-flow-f1"));
    expect(onRemoveFlow).toHaveBeenCalledWith("f1");
  });

  it("does not propagate click to onSelectFlow", async () => {
    const user = userEvent.setup();
    const onSelectFlow = jest.fn();
    const onRemoveFlow = jest.fn();
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    renderPanel({ selectedVersionByFlow, onRemoveFlow, onSelectFlow });

    await user.click(screen.getByTestId("detach-flow-f1"));
    expect(onSelectFlow).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Undo button
// ---------------------------------------------------------------------------

describe("Undo button", () => {
  it("triggers onUndoRemoveFlow callback when clicking the undo button", async () => {
    const user = userEvent.setup();
    const onUndoRemoveFlow = jest.fn();
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    const removedFlowIds = new Set(["f1"]);
    renderPanel({ selectedVersionByFlow, removedFlowIds, onUndoRemoveFlow });

    await user.click(screen.getByTestId("undo-remove-flow-f1"));
    expect(onUndoRemoveFlow).toHaveBeenCalledWith("f1");
  });

  it("undo button only visible for removed flows", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
      ["f2", { versionId: "v2", versionTag: "v2.0" }],
    ]);
    const removedFlowIds = new Set(["f1"]);
    renderPanel({ selectedVersionByFlow, removedFlowIds });

    expect(screen.getByTestId("undo-remove-flow-f1")).toBeInTheDocument();
    expect(screen.queryByTestId("undo-remove-flow-f2")).not.toBeInTheDocument();
  });

  it("undo button not visible when onUndoRemoveFlow is not provided", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    const removedFlowIds = new Set(["f1"]);
    renderPanel({
      selectedVersionByFlow,
      removedFlowIds,
      onUndoRemoveFlow: undefined,
    });

    expect(screen.queryByTestId("undo-remove-flow-f1")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Click on flow item
// ---------------------------------------------------------------------------

describe("Click on flow item", () => {
  it("triggers onSelectFlow with the flow id", async () => {
    const user = userEvent.setup();
    const onSelectFlow = jest.fn();
    renderPanel({ onSelectFlow });

    await user.click(screen.getByTestId("flow-item-f2"));
    expect(onSelectFlow).toHaveBeenCalledWith("f2");
  });
});
