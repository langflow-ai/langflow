import { act, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import ToolsTable from "../index";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  default: ({ name }: any) => <span>{name}</span>,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  default: ({ children }: any) => <div>{children}</div>,
}));

jest.mock("@/components/ui/input", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  Input: ({ value, onChange, placeholder }: any) => (
    <input
      data-testid="search-input"
      value={value ?? ""}
      onChange={onChange}
      placeholder={placeholder}
    />
  ),
}));

jest.mock("@/components/ui/button", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} data-testid={props["data-testid"]}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/textarea", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  Textarea: ({ value, onChange }: any) => (
    <textarea data-testid="textarea" value={value ?? ""} onChange={onChange} />
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

const mockSetSidebarOpen = jest.fn();
jest.mock("@/components/ui/sidebar", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  Sidebar: ({ children }: any) => <div data-testid="sidebar">{children}</div>,
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  SidebarContent: ({ children }: any) => <div>{children}</div>,
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  SidebarFooter: ({ children }: any) => <div>{children}</div>,
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  SidebarGroup: ({ children }: any) => <div>{children}</div>,
  // biome-ignore lint/suspicious/noExplicitAny: legacy mock
  SidebarGroupContent: ({ children }: any) => <div>{children}</div>,
  useSidebar: () => ({ setOpen: mockSetSidebarOpen }),
}));

jest.mock("@/utils/stringManipulation", () => ({
  parseString: (str: string) => str,
  sanitizeMcpName: (str: string) => str,
}));

// -------------------------------------------------------------------
// Shared mutable state for the TableComponent mock.
// We use module-level variables so the test can reach into the mock's
// captured callbacks and fake API without fighting React re-render
// lifecycle issues.
// -------------------------------------------------------------------
// biome-ignore lint/suspicious/noExplicitAny: legacy mock
let lastTableProps: any = null;
// Minimal grid API instance shared across all renders of the mock.
const mockSetGridOption = jest.fn();
const mockForEachNode = jest.fn();
const mockGetSelectedRows = jest.fn(() => []);

const fakeApi = {
  setGridOption: mockSetGridOption,
  forEachNode: mockForEachNode,
  getSelectedRows: mockGetSelectedRows,
  applyTransaction: jest.fn(),
};

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    default: React.forwardRef((props: any, ref: any) => {
      lastTableProps = props;

      // Attach the stable fake API via the ref every render so the
      // component's useEffect can call agGrid.current.api.*
      React.useEffect(() => {
        const refObj = { api: fakeApi };
        if (typeof ref === "function") ref(refObj);
        else if (ref) ref.current = refObj;

        // Trigger onGridReady so isGridReady state is set to true
        props.onGridReady?.();
      }, []);

      return (
        <div data-testid="table-component">
          {/* biome-ignore lint/suspicious/noExplicitAny: legacy mock */}
          {(props.rowData ?? []).map((row: any) => (
            <div
              key={row.name}
              data-testid={`row-body-${row.name}`}
              onClick={() =>
                props.onRowClicked?.({
                  data: row,
                  event: { target: document.createElement("div") },
                })
              }
            />
          ))}
        </div>
      );
    }),
  }),
);

// -------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------

const makeRows = () => [
  {
    name: "tool_a",
    display_name: "Tool A",
    description: "desc a",
    display_description: "desc a",
    status: true,
    tags: [],
    readonly: false,
  },
  {
    name: "tool_b",
    display_name: "Tool B",
    description: "desc b",
    display_description: "desc b",
    status: false,
    tags: [],
    readonly: false,
  },
];

// biome-ignore lint/suspicious/noExplicitAny: legacy mock
function makeProps(overrides: Record<string, any> = {}) {
  return {
    rows: makeRows(),
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    data: [] as any[],
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    setData: jest.fn((d: any[]) => {}),
    isAction: false,
    placeholder: "Select tools",
    open: true,
    handleOnNewValue: jest.fn(),
    ...overrides,
  };
}

// -------------------------------------------------------------------
// Tests
// -------------------------------------------------------------------

describe("ToolsTable – selection behaviour", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    lastTableProps = null;
  });

  it("always passes suppressRowClickSelection=true to TableComponent", async () => {
    render(<ToolsTable {...makeProps()} />);

    await waitFor(() => expect(lastTableProps).not.toBeNull());

    expect(lastTableProps.suppressRowClickSelection).toBe(true);
  });

  it("selection-reapply effect calls setGridOption with true, never with false", async () => {
    // Make forEachNode no-op so the effect completes without errors
    mockForEachNode.mockImplementation(() => {});

    render(<ToolsTable {...makeProps()} />);

    await waitFor(() =>
      expect(mockSetGridOption).toHaveBeenCalledWith(
        "suppressRowClickSelection",
        true,
      ),
    );

    // Must never have been called with false
    const badCalls = mockSetGridOption.mock.calls.filter(
      ([opt, val]: [string, unknown]) =>
        opt === "suppressRowClickSelection" && val === false,
    );
    expect(badCalls).toHaveLength(0);
  });

  it("row-body click opens sidebar but does NOT trigger handleSelectionChanged", async () => {
    // Capture setData so we can pass the populated data back
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    let storedData: any[] = [];
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    const setData = jest.fn((d: any[]) => {
      storedData = d;
    });
    const props = makeProps({ setData });

    const { rerender } = render(<ToolsTable {...props} />);

    // After the open-effect runs, re-render with the populated data so rows appear
    await waitFor(() => expect(storedData.length).toBeGreaterThan(0));
    rerender(<ToolsTable {...props} data={storedData} />);

    await waitFor(() =>
      expect(screen.getByTestId("row-body-tool_a")).toBeInTheDocument(),
    );

    const callsBefore = mockSetGridOption.mock.calls.length;

    act(() => {
      screen.getByTestId("row-body-tool_a").click();
    });

    // Sidebar must open
    expect(mockSetSidebarOpen).toHaveBeenCalledWith(true);

    // No new setGridOption calls (would indicate handleSelectionChanged fired
    // and re-applied selections — which would only happen if row-body click
    // incorrectly changed selectedRows state)
    expect(mockSetGridOption.mock.calls.length).toBe(callsBefore);
  });

  it("emits correct status flags via handleOnNewValue when modal closes", async () => {
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    let storedData: any[] = [];
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    const setData = jest.fn((d: any[]) => {
      storedData = d;
    });
    const handleOnNewValue = jest.fn();
    const rows = makeRows(); // tool_a: status=true, tool_b: status=false

    // Set up forEachNode so the selection-reapply effect works correctly.
    // tool_a has status:true so it will be in selectedRows after open.
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    mockForEachNode.mockImplementation((cb: (node: any) => void) => {
      storedData.forEach((row) =>
        cb({
          data: row,
          isSelected: jest.fn(() => row.status),
          setSelected: jest.fn(),
        }),
      );
    });

    const props = makeProps({ setData, handleOnNewValue, rows });
    const { rerender } = render(<ToolsTable {...props} />);

    await waitFor(() => expect(storedData.length).toBeGreaterThan(0));

    // Close the modal → triggers the handleOnNewValue effect
    rerender(<ToolsTable {...props} data={storedData} open={false} />);

    await waitFor(() => expect(handleOnNewValue).toHaveBeenCalled());

    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    const emitted: any[] = handleOnNewValue.mock.calls[0][0].value;
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    const emittedA = emitted.find((r: any) => r.name === "tool_a");
    // biome-ignore lint/suspicious/noExplicitAny: legacy mock
    const emittedB = emitted.find((r: any) => r.name === "tool_b");
    // tool_a was in selectedRows (status=true on open) → emitted as status:true
    expect(emittedA?.status).toBe(true);
    // tool_b was not in selectedRows → emitted as status:false
    expect(emittedB?.status).toBe(false);
  });
});
