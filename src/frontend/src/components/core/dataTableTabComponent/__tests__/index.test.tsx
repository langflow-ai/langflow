import { render, screen } from "@testing-library/react";
import type { SelectionChangedEvent } from "ag-grid-community";
import React from "react";
import DataTableTab, { type DataTableTabProps } from "../index";

// TableComponent is mocked to a prop-capturing stub (forwardRef because the
// shell forwards `tableRef` to it), so the test asserts what the shell composes
// rather than AG-Grid's rendering.
interface MockTableProps {
  className?: string;
  gridOptions?: Record<string, unknown>;
  onSelectionChanged?: (event: SelectionChangedEvent) => void;
}

let mockLatestTableProps: MockTableProps = {};
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => {
    const ReactActual = jest.requireActual<typeof React>("react");
    return {
      __esModule: true,
      default: ReactActual.forwardRef((props: MockTableProps, _ref) => {
        mockLatestTableProps = props;
        return <div data-testid="mock-table" />;
      }),
    };
  },
);

type Row = { id: string; name: string };

function makeProps(
  overrides: Partial<DataTableTabProps<Row>> = {},
): DataTableTabProps<Row> {
  return {
    columnDefs: [{ field: "name" }],
    rowData: [{ id: "1", name: "Alpha" }],
    isLoading: false,
    loadingState: <div data-testid="loading" />,
    emptyState: <div data-testid="empty" />,
    searchPlaceholder: "Search",
    searchInputTestId: "search-input",
    quickFilterText: "",
    setQuickFilterText: jest.fn(),
    toolbarActions: <div data-testid="toolbar" />,
    setSelectedRows: jest.fn(),
    setQuantitySelected: jest.fn(),
    quantitySelected: 0,
    isShiftPressed: false,
    ...overrides,
  };
}

function renderTab(overrides: Partial<DataTableTabProps<Row>> = {}) {
  return render(<DataTableTab<Row> {...makeProps(overrides)} />);
}

beforeEach(() => {
  mockLatestTableProps = {};
  jest.useRealTimers();
});

describe("DataTableTab", () => {
  it("renders only the loading state while loading (no table, no search)", () => {
    renderTab({ isLoading: true });

    expect(screen.getByTestId("loading")).toBeTruthy();
    expect(screen.queryByTestId("mock-table")).toBeNull();
    expect(screen.queryByTestId("search-input")).toBeNull();
  });

  it("renders only the empty state when there are no rows", () => {
    renderTab({ rowData: [] });

    expect(screen.getByTestId("empty")).toBeTruthy();
    expect(screen.queryByTestId("mock-table")).toBeNull();
  });

  it("mounts children in the table, loading and empty states", () => {
    const child = <div data-testid="child-modal" />;

    const { rerender } = render(
      <DataTableTab<Row> {...makeProps({ children: child })} />,
    );
    expect(screen.getByTestId("child-modal")).toBeTruthy();

    rerender(
      <DataTableTab<Row>
        {...makeProps({ isLoading: true, children: child })}
      />,
    );
    expect(screen.getByTestId("child-modal")).toBeTruthy();

    rerender(
      <DataTableTab<Row> {...makeProps({ rowData: [], children: child })} />,
    );
    expect(screen.getByTestId("child-modal")).toBeTruthy();
  });

  it("merges consumer gridOptions on top of the shared defaults rather than replacing them", () => {
    renderTab({ gridOptions: { ensureDomOrder: false, rowBuffer: 5 } });

    expect(mockLatestTableProps.gridOptions).toEqual({
      stopEditingWhenCellsLoseFocus: true,
      ensureDomOrder: false, // consumer override wins
      colResizeDefault: "shift",
      rowBuffer: 5, // consumer addition preserved
    });
  });

  it("merges tableClassName into the base table classes", () => {
    renderTab({ tableClassName: "ag-knowledge-table" });

    expect(mockLatestTableProps.className).toContain("ag-no-border");
    expect(mockLatestTableProps.className).toContain("ag-knowledge-table");
  });

  it("wraps the table via renderTableWrapper when provided", () => {
    renderTab({
      renderTableWrapper: (table) => (
        <div data-testid="table-wrapper">{table}</div>
      ),
    });

    const wrapper = screen.getByTestId("table-wrapper");
    expect(wrapper).toBeTruthy();
    expect(wrapper.querySelector('[data-testid="mock-table"]')).toBeTruthy();
  });

  it("forwards selected rows immediately and defers the zero by 300ms", () => {
    jest.useFakeTimers();
    const setSelectedRows = jest.fn();
    const setQuantitySelected = jest.fn();
    renderTab({ setSelectedRows, setQuantitySelected });

    const onSelectionChanged = mockLatestTableProps.onSelectionChanged;
    expect(onSelectionChanged).toBeDefined();

    const rows = [{ id: "1", name: "Alpha" }];
    onSelectionChanged?.({
      api: { getSelectedRows: () => rows },
    } as unknown as SelectionChangedEvent);
    expect(setSelectedRows).toHaveBeenLastCalledWith(rows);
    expect(setQuantitySelected).toHaveBeenLastCalledWith(1);

    setQuantitySelected.mockClear();
    onSelectionChanged?.({
      api: { getSelectedRows: () => [] },
    } as unknown as SelectionChangedEvent);
    expect(setSelectedRows).toHaveBeenLastCalledWith([]);
    // the zero is not written synchronously…
    expect(setQuantitySelected).not.toHaveBeenCalled();
    // …only after the 300ms debounce.
    jest.advanceTimersByTime(300);
    expect(setQuantitySelected).toHaveBeenCalledWith(0);
  });
});
