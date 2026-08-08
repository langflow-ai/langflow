import { render, waitFor } from "@testing-library/react";
import type { ForwardedRef } from "react";
import TableComponent from "../index";

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

        return <div role="treegrid" />;
      },
    ),
  };
});

describe("TableComponent accessibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
