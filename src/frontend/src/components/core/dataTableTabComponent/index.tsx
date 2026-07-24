import type { ColDef, SelectionChangedEvent } from "ag-grid-community";
import type { AgGridReact, AgGridReactProps } from "ag-grid-react";
import type { ElementRef, ReactNode, Ref } from "react";
import TableComponent, {
  type TableComponentProps,
} from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";

export interface DataTableTabProps<TData> {
  columnDefs: ColDef[];
  /** Row data already sorted by the consumer tab. */
  rowData: TData[];
  isLoading: boolean;
  /** Rendered as-is (no shell wrappers) while `isLoading` is true. */
  loadingState: ReactNode;
  /** Rendered as-is (no shell wrappers) when `rowData` is empty. */
  emptyState: ReactNode;
  searchPlaceholder: string;
  searchInputTestId: string;
  searchInputAriaLabel?: string;
  searchInputClassName?: string;
  quickFilterText: string;
  setQuickFilterText: (text: string) => void;
  /** Right side of the header row (primary/delete actions, incl. their own container). */
  toolbarActions: ReactNode;
  setSelectedRows: (rows: TData[]) => void;
  setQuantitySelected: (quantity: number) => void;
  quantitySelected: number;
  isShiftPressed: boolean;
  tableRef?: Ref<ElementRef<typeof AgGridReact>>;
  tableClassName?: string;
  editable?: TableComponentProps["editable"];
  onCellKeyDown?: AgGridReactProps["onCellKeyDown"];
  onRowClicked?: AgGridReactProps["onRowClicked"];
  getRowId?: AgGridReactProps["getRowId"];
  /** Merged on top of the shared grid options. */
  gridOptions?: AgGridReactProps["gridOptions"];
  /** Wraps the table container (e.g. a file-drop zone). */
  renderTableWrapper?: (table: JSX.Element) => ReactNode;
  /** Feature-specific modals rendered inside the shell root. */
  children?: ReactNode;
}

const DataTableTab = <TData,>({
  columnDefs,
  rowData,
  isLoading,
  loadingState,
  emptyState,
  searchPlaceholder,
  searchInputTestId,
  searchInputAriaLabel,
  searchInputClassName,
  quickFilterText,
  setQuickFilterText,
  toolbarActions,
  setSelectedRows,
  setQuantitySelected,
  quantitySelected,
  isShiftPressed,
  tableRef,
  tableClassName,
  editable,
  onCellKeyDown,
  onRowClicked,
  getRowId,
  gridOptions,
  renderTableWrapper,
  children,
}: DataTableTabProps<TData>) => {
  const handleSelectionChanged = (event: SelectionChangedEvent) => {
    const selectedRows = event.api.getSelectedRows();
    setSelectedRows(selectedRows);
    if (selectedRows.length > 0) {
      setQuantitySelected(selectedRows.length);
    } else {
      setTimeout(() => {
        setQuantitySelected(0);
      }, 300);
    }
  };

  if (isLoading) {
    return <>{loadingState}</>;
  }

  if (rowData.length === 0) {
    return <>{emptyState}</>;
  }

  const table = (
    <div className="relative h-full">
      <TableComponent
        rowHeight={45}
        headerHeight={45}
        cellSelection={false}
        tableOptions={{ hide_options: true }}
        suppressRowClickSelection={!isShiftPressed}
        rowSelection="multiple"
        onSelectionChanged={handleSelectionChanged}
        onRowClicked={onRowClicked}
        onCellKeyDown={onCellKeyDown}
        editable={editable}
        columnDefs={columnDefs}
        rowData={rowData}
        className={cn(
          "ag-no-border group w-full",
          tableClassName,
          isShiftPressed && quantitySelected > 0 && "no-select-cells",
        )}
        pagination
        ref={tableRef}
        quickFilterText={quickFilterText}
        getRowId={getRowId}
        gridOptions={{
          stopEditingWhenCellsLoseFocus: true,
          ensureDomOrder: true,
          colResizeDefault: "shift",
          ...gridOptions,
        }}
      />
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex justify-between">
        <div className="flex w-full xl:w-5/12">
          <Input
            icon="Search"
            data-testid={searchInputTestId}
            type="text"
            placeholder={searchPlaceholder}
            aria-label={searchInputAriaLabel}
            className={cn("w-full", searchInputClassName)}
            value={quickFilterText || ""}
            onChange={(event) => setQuickFilterText(event.target.value)}
          />
        </div>
        {toolbarActions}
      </div>
      <div className="flex h-full flex-col py-4">
        {renderTableWrapper ? renderTableWrapper(table) : table}
      </div>
      {children}
    </div>
  );
};

export default DataTableTab;
