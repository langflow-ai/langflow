import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionItem } from "../types";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import { ConnectionSearchList } from "../components/connection-search-list";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConnection(
  overrides: Partial<ConnectionItem> & { id: string; name: string },
): ConnectionItem {
  return {
    connectionId: `cid-${overrides.id}`,
    variableCount: 0,
    isNew: false,
    environmentVariables: {},
    ...overrides,
  };
}

const connections: ConnectionItem[] = [
  makeConnection({ id: "conn-1", name: "Production API" }),
  makeConnection({ id: "conn-2", name: "Staging API", isNew: true }),
  makeConnection({ id: "conn-3", name: "Development Env" }),
];

const defaultProps = {
  connections,
  selectedConnections: new Set<string>(),
  onToggleConnection: jest.fn(),
  onSwitchToCreate: jest.fn(),
};

function renderList(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(<ConnectionSearchList {...props} />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Search filtering
// ---------------------------------------------------------------------------

describe("Search filtering", () => {
  it("filters connections case-insensitively", async () => {
    const user = userEvent.setup();
    renderList();

    await user.type(
      screen.getByPlaceholderText("Search connections..."),
      "production",
    );
    expect(screen.getByText("Production API")).toBeInTheDocument();
    expect(screen.queryByText("Staging API")).not.toBeInTheDocument();
    expect(screen.queryByText("Development Env")).not.toBeInTheDocument();
  });

  it("filters connections by id (not just name)", async () => {
    const user = userEvent.setup();
    renderList();

    // Type a connection ID that doesn't appear in any name
    await user.type(
      screen.getByPlaceholderText("Search connections..."),
      "conn-2",
    );
    expect(screen.getByText("Staging API")).toBeInTheDocument();
    expect(screen.queryByText("Production API")).not.toBeInTheDocument();
    expect(screen.queryByText("Development Env")).not.toBeInTheDocument();
  });

  it("shows empty state when no connections match", async () => {
    const user = userEvent.setup();
    renderList();

    await user.type(
      screen.getByPlaceholderText("Search connections..."),
      "zzz-no-match",
    );
    expect(screen.getByText(/No connections match/)).toBeInTheDocument();
  });

  it("search query clears correctly", async () => {
    const user = userEvent.setup();
    renderList();

    const input = screen.getByPlaceholderText("Search connections...");
    await user.type(input, "Production");
    expect(screen.queryByText("Staging API")).not.toBeInTheDocument();

    await user.clear(input);
    expect(screen.getByText("Production API")).toBeInTheDocument();
    expect(screen.getByText("Staging API")).toBeInTheDocument();
    expect(screen.getByText("Development Env")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// New connections sort first
// ---------------------------------------------------------------------------

describe("Sorting", () => {
  it("new connections (isNew=true) sort first", () => {
    renderList();
    // CheckboxSelectItem renders a <label> with the connection name inside.
    // "Staging API" (isNew=true) should come before the others.
    const allNames = screen.getAllByText(/API|Env/).map((el) => el.textContent);
    const stagingIndex = allNames.findIndex((t) => t?.includes("Staging API"));
    const prodIndex = allNames.findIndex((t) => t?.includes("Production API"));
    expect(stagingIndex).toBeLessThan(prodIndex);
  });
});

// ---------------------------------------------------------------------------
// Empty state when no connections
// ---------------------------------------------------------------------------

describe("Empty state (no connections)", () => {
  it("shows empty state when connections array is empty", () => {
    renderList({ connections: [] });
    expect(screen.getByText("No connections yet")).toBeInTheDocument();
    expect(
      screen.getByText("Create your first connection"),
    ).toBeInTheDocument();
  });

  it("clicking 'Create your first connection' calls onSwitchToCreate", async () => {
    const user = userEvent.setup();
    const onSwitchToCreate = jest.fn();
    renderList({ connections: [], onSwitchToCreate });

    await user.click(screen.getByText("Create your first connection"));
    expect(onSwitchToCreate).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Connection selection toggle
// ---------------------------------------------------------------------------

describe("Connection selection toggle", () => {
  it("calls onToggleConnection when clicking a connection", async () => {
    const user = userEvent.setup();
    const onToggleConnection = jest.fn();
    renderList({ onToggleConnection });

    await user.click(screen.getByText("Production API"));
    expect(onToggleConnection).toHaveBeenCalledWith("conn-1");
  });

  it("selected connections have checked checkbox", () => {
    const selectedConnections = new Set(["conn-2"]);
    renderList({ selectedConnections });

    // CheckboxSelectItem renders an <input type="checkbox"> with checked state
    const checkbox = screen.getByTestId("connection-item-conn-2");
    const input = checkbox.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(input.checked).toBe(true);
  });
});
