import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ForwardedRef } from "react";
import TableComponent from "../index";

const mockTextTriggerClick = jest.fn();
const mockSetGridAriaProperty = jest.fn();
const mockApi = {
  applyColumnState: jest.fn(),
  getColumnDefs: jest.fn(() => []),
  getColumnState: jest.fn(() => []),
  getColumns: jest.fn(() => []),
  getSelectedRows: jest.fn(() => []),
  hideOverlay: jest.fn(),
  isDestroyed: jest.fn(() => false),
  setGridAriaProperty: mockSetGridAriaProperty,
  setGridOption: jest.fn(),
  sizeColumnsToFit: jest.fn(),
};

jest.mock("ag-grid-react", () => {
  const React = require("react");
  type MockGridReadyParams = {
    api: typeof mockApi;
    columnApi: { getAllGridColumns: jest.Mock };
  };
  type MockAgGridProps = {
    onCellKeyDown?: (event: { event: KeyboardEvent }) => void;
    onGridReady?: (params: MockGridReadyParams) => void;
  };

  return {
    AgGridReact: React.forwardRef(
      (props: MockAgGridProps, ref: ForwardedRef<{ api: typeof mockApi }>) => {
        React.useImperativeHandle(ref, () => ({ api: mockApi }));
        React.useEffect(() => {
          props.onGridReady?.({
            api: mockApi,
            columnApi: { getAllGridColumns: jest.fn(() => []) },
          });
        }, [props.onGridReady]);

        return (
          <div role="treegrid">
            <div
              data-testid="mock-grid-cell"
              onKeyDown={(event) =>
                props.onCellKeyDown?.({ event: event.nativeEvent })
              }
              role="gridcell"
            >
              <button
                data-langflow-text-cell-trigger
                data-testid="mock-text-trigger"
                onClick={mockTextTriggerClick}
                type="button"
              >
                View text
              </button>
            </div>
          </div>
        );
      },
    ),
  };
});

describe("TableComponent accessibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it.each(["Enter", " "])(
    "does not synthetically activate a focused text modal trigger with %p",
    (key) => {
      const onCellKeyDown = jest.fn();
      render(
        <TableComponent
          columnDefs={[{ field: "name" }]}
          onCellKeyDown={onCellKeyDown}
          rowData={[{ name: "Run 1" }]}
        />,
      );

      fireEvent.keyDown(screen.getByTestId("mock-text-trigger"), { key });

      expect(onCellKeyDown).not.toHaveBeenCalled();
      expect(mockTextTriggerClick).not.toHaveBeenCalled();
    },
  );

  it("synthetically activates a text modal trigger from its grid cell", () => {
    render(
      <TableComponent
        columnDefs={[{ field: "name" }]}
        rowData={[{ name: "Run 1" }]}
      />,
    );

    fireEvent.keyDown(screen.getByTestId("mock-grid-cell"), { key: "Enter" });

    expect(mockTextTriggerClick).toHaveBeenCalledTimes(1);
  });

  it("applies aria-label to the ag-grid panel", async () => {
    render(
      <TableComponent
        aria-label="Trace runs table"
        columnDefs={[{ field: "name" }]}
        rowData={[{ name: "Run 1" }]}
      />,
    );

    await waitFor(() => {
      expect(mockSetGridAriaProperty).toHaveBeenCalledWith(
        "label",
        "Trace runs table",
      );
    });
  });
});
