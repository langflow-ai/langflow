import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import { VersionPanel } from "../components/step-attach-flows-version-panel";

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

function makeVersion(
  overrides: Partial<FlowVersionEntry> & { id: string },
): FlowVersionEntry {
  return {
    flow_id: "f1",
    user_id: "u1",
    version_number: 1,
    version_tag: `v${overrides.id}`,
    description: null,
    created_at: "2025-03-15T12:00:00Z",
    ...overrides,
  };
}

const selectedFlow = makeFlow({ id: "f1", name: "My Flow" });

const versions: FlowVersionEntry[] = [
  makeVersion({
    id: "v1",
    version_tag: "v1.0",
    created_at: "2025-01-10T08:00:00Z",
  }),
  makeVersion({
    id: "v2",
    version_tag: "v2.0",
    created_at: "2025-03-15T12:00:00Z",
  }),
];

const defaultProps = {
  selectedFlow: selectedFlow as FlowType | undefined,
  versions,
  isLoadingVersions: false,
  selectedVersionByFlow: new Map<
    string,
    { versionId: string; versionTag: string }
  >(),
  onAttach: jest.fn(),
};

function renderPanel(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(<VersionPanel {...props} />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// No flow selected
// ---------------------------------------------------------------------------

describe("No flow selected", () => {
  it("shows placeholder message when no flow is selected", () => {
    renderPanel({ selectedFlow: undefined });
    expect(
      screen.getByText("Select a flow to see versions"),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("Loading state", () => {
  it("shows 'Loading versions...' when loading", () => {
    renderPanel({ isLoadingVersions: true });
    expect(screen.getByText("Loading versions...")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("No versions found", () => {
  it("shows empty state when no versions exist", () => {
    renderPanel({ versions: [] });
    expect(screen.getByText("No versions found")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Rendering version items
// ---------------------------------------------------------------------------

describe("Rendering version items", () => {
  it("renders version items with version tags", () => {
    renderPanel();
    expect(screen.getByText("v1.0")).toBeInTheDocument();
    expect(screen.getByText("v2.0")).toBeInTheDocument();
  });

  it("renders version items with dates", () => {
    renderPanel();
    // The component uses toLocaleDateString() -- verify date text is present
    const v1Date = new Date("2025-01-10T08:00:00Z").toLocaleDateString();
    const v2Date = new Date("2025-03-15T12:00:00Z").toLocaleDateString();
    expect(screen.getByTestId("version-item-v1").textContent).toContain(
      v1Date,
    );
    expect(screen.getByTestId("version-item-v2").textContent).toContain(
      v2Date,
    );
  });
});

// ---------------------------------------------------------------------------
// ATTACHED badge for currently attached version
// ---------------------------------------------------------------------------

describe("ATTACHED badge", () => {
  it("shows ATTACHED badge for the currently attached version", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    renderPanel({ selectedVersionByFlow });
    expect(screen.getByText("ATTACHED")).toBeInTheDocument();
  });

  it("attached version has highlighted styling", () => {
    const selectedVersionByFlow = new Map([
      ["f1", { versionId: "v1", versionTag: "v1.0" }],
    ]);
    renderPanel({ selectedVersionByFlow });
    const button = screen.getByTestId("version-item-v1");
    expect(button.className).toContain("border-accent-blue-foreground");

    const otherButton = screen.getByTestId("version-item-v2");
    expect(otherButton.className).not.toContain(
      "border-accent-blue-foreground",
    );
  });

  it("does not show ATTACHED badge when no version is attached", () => {
    renderPanel();
    expect(screen.queryByText("ATTACHED")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Click triggers onAttach
// ---------------------------------------------------------------------------

describe("Click triggers onAttach", () => {
  it("calls onAttach with version id when clicking a version", async () => {
    const user = userEvent.setup();
    const onAttach = jest.fn();
    renderPanel({ onAttach });

    await user.click(screen.getByTestId("version-item-v2"));
    expect(onAttach).toHaveBeenCalledWith("v2");
  });
});
