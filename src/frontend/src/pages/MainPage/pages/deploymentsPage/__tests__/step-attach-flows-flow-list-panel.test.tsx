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

function selectedVersion(
  flowId: string,
  versionId: string,
  versionTag: string,
) {
  return {
    key: `${flowId}:${versionId}`,
    flowId,
    versionId,
    versionTag,
  };
}

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
  selectedVersionByFlow: new Map<string, ReturnType<typeof selectedVersion>>(),
  attachedConnectionByFlow: new Map<string, string[]>(),
  connections,
  removedFlowIds: new Set<string>(),
  onSelectFlow: jest.fn(),
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
// Attached version badges
// ---------------------------------------------------------------------------

describe("Attached version badges", () => {
  it("shows version count badge for flows in selectedVersionByFlow map", () => {
    const selectedVersionByFlow = new Map([
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
    ]);
    renderPanel({ selectedVersionByFlow });
    expect(screen.getByText("1 VERSION")).toBeInTheDocument();
  });

  it("does not show version count badge for flows not in the map", () => {
    renderPanel();
    expect(screen.queryByText(/VERSION/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// REMOVED badge and opacity
// ---------------------------------------------------------------------------

describe("REMOVED badge and opacity", () => {
  it("shows REMOVED badge for flows in removedFlowIds set", () => {
    const selectedVersionByFlow = new Map([
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
    ]);
    const removedFlowIds = new Set(["f1:v1"]);
    renderPanel({ selectedVersionByFlow, removedFlowIds });
    expect(screen.getByText("REMOVED")).toBeInTheDocument();
    expect(screen.queryByText("1 VERSION")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Version labels
// ---------------------------------------------------------------------------

describe("Version labels", () => {
  it("shows version label when attached and not removed", () => {
    const selectedVersionByFlow = new Map([
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
    ]);
    renderPanel({ selectedVersionByFlow });
    expect(screen.getByText("v1.0")).toBeInTheDocument();
  });

  it("does not show version label for removed flows", () => {
    const selectedVersionByFlow = new Map([
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
    ]);
    const removedFlowIds = new Set(["f1:v1"]);
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
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
    ]);
    const attachedConnectionByFlow = new Map([["f1:v1", ["conn-1", "conn-2"]]]);
    renderPanel({ selectedVersionByFlow, attachedConnectionByFlow });
    expect(
      screen.getByText("Prod Connection, Dev Connection"),
    ).toBeInTheDocument();
  });

  it("does not show connection names for removed flows", () => {
    const selectedVersionByFlow = new Map([
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
    ]);
    const attachedConnectionByFlow = new Map([["f1:v1", ["conn-1"]]]);
    const removedFlowIds = new Set(["f1:v1"]);
    renderPanel({
      selectedVersionByFlow,
      attachedConnectionByFlow,
      removedFlowIds,
    });
    expect(screen.queryByText("Prod Connection")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Removed version summary
// ---------------------------------------------------------------------------

describe("Removed version summary", () => {
  it("shows removed count when some versions are removed and others stay active", () => {
    const selectedVersionByFlow = new Map([
      ["f1:v1", selectedVersion("f1", "v1", "v1.0")],
      ["f1:v2", selectedVersion("f1", "v2", "v2.0")],
    ]);

    renderPanel({
      selectedVersionByFlow,
      removedFlowIds: new Set(["f1:v2"]),
    });

    expect(screen.getByText("1 removed")).toBeInTheDocument();
    expect(screen.getByText("1 VERSION")).toBeInTheDocument();
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
