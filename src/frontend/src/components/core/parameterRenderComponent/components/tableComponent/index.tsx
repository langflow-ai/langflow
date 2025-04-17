import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  DEFAULT_TABLE_ALERT_MSG,
  DEFAULT_TABLE_ALERT_TITLE,
  NO_COLUMN_DEFINITION_ALERT_DESCRIPTION,
  NO_COLUMN_DEFINITION_ALERT_TITLE,
} from "@/constants/constants";
import { useDarkStore } from "@/stores/darkStore";
import "@/style/ag-theme-shadcn.css"; // Custom CSS applied to the grid
import { TableOptionsTypeAPI } from "@/types/api";
import { cn } from "@/utils/utils";
import { ColDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact, AgGridReactProps } from "ag-grid-react";
import cloneDeep from "lodash";
import { ElementRef, forwardRef, useRef, useState } from "react";
import TableOptions from "./components/TableOptions";
import resetGrid from "./utils/reset-grid-columns";

export interface TableComponentProps extends AgGridReactProps {
  columnDefs: NonNullable<ColDef<any, any>[]>;
  rowData: NonNullable<AgGridReactProps["rowData"]>;
  displayEmptyAlert?: boolean;
  alertTitle?: string;
  alertDescription?: string;
  editable?:
    | boolean
    | string[]
    | {
        field: string;
        onUpdate: (value: any) => void;
        editableCell: boolean;
      }[];
  pagination?: boolean;
  onDelete?: () => void;
  onDuplicate?: () => void;
  addRow?: () => void;
  tableOptions?: TableOptionsTypeAPI;
  paginationInfo?: string;
}

const TableComponent = forwardRef<
  ElementRef<typeof AgGridReact>,
  TableComponentProps
>(
  (
    {
      alertTitle = DEFAULT_TABLE_ALERT_TITLE,
      alertDescription = DEFAULT_TABLE_ALERT_MSG,
      displayEmptyAlert = true,
      ...props
    },
    ref,
  ) => {
    let colDef = props.columnDefs
      .filter((col) => !col.hide)
      .map((col, index, filteredArray) => {
        let newCol = {
          ...col,
        };

        if (index !== filteredArray.length - 1) {
          newCol = {
            ...newCol,
            suppressSizeToFit: true,
          };
        }
        if (props.rowSelection && props.onSelectionChanged && index === 0) {
          newCol = {
            ...newCol,
            checkboxSelection: true,
            headerCheckboxSelection: true,
            headerCheckboxSelectionFilteredOnly: true,
          };
        }
        if (
          (typeof props.tableOptions?.block_hide === "boolean" &&
            props.tableOptions?.block_hide) ||
          (Array.isArray(props.tableOptions?.block_hide) &&
            props.tableOptions?.block_hide.includes(newCol.field ?? ""))
        ) {
          newCol = {
            ...newCol,
            lockVisible: true,
          };
        }
        if (
          (typeof props.editable === "boolean" && props.editable) ||
          (Array.isArray(props.editable) &&
            props.editable.every((field) => typeof field === "string") &&
            (props.editable as Array<string>).includes(newCol.field ?? ""))
        ) {
          newCol = {
            ...newCol,
            editable: true,
          };
        }
        if (
          Array.isArray(props.editable) &&
          props.editable.every((field) => typeof field === "object")
        ) {
          const field = (
            props.editable as Array<{
              field: string;
              onUpdate: (value: any) => void;
              editableCell: boolean;
            }>
          ).find((field) => field.field === newCol.field);
          if (field) {
            newCol = {
              ...newCol,
              editable: field.editableCell,
              onCellValueChanged: (e) => field.onUpdate(e),
            };
          }
        }
        return newCol;
      });
    // @ts-ignore
    const realRef: React.MutableRefObject<AgGridReact> =
      useRef<AgGridReact | null>(null);
    const dark = useDarkStore((state) => state.dark);
    const initialColumnDefs = useRef(colDef);
    const [columnStateChange, setColumnStateChange] = useState(false);
    // Only use visible columns for the store reference
    const storeReference = props.columnDefs
      .filter((col) => !col.hide)
      .map((e) => e.headerName)
      .join("_");

    const onGridReady = (params) => {
      // @ts-ignore
      realRef.current = params;
      const updatedColumnDefs = [...colDef];
      params.api.setGridOption("columnDefs", updatedColumnDefs);
      const customInit = localStorage.getItem(storeReference);
      initialColumnDefs.current = params.api.getColumnDefs();
      if (customInit && realRef.current) {
        realRef.current.api.applyColumnState({
          state: JSON.parse(customInit),
          applyOrder: true,
        });
      }
      setTimeout(() => {
        if (customInit && realRef.current) {
          setColumnStateChange(true);
        } else {
          setColumnStateChange(false);
        }
      }, 50);
      setTimeout(() => {
        if (!realRef?.current?.api?.isDestroyed) {
          realRef?.current?.api?.hideOverlay();
          // Force column fit after hiding overlay to ensure proper layout
          realRef?.current?.api?.sizeColumnsToFit();
        }
      }, 1000);
      if (props.onGridReady) props.onGridReady(params);
    };
    const onColumnMoved = (params) => {
      const updatedColumnDefs = cloneDeep(
        params.columnApi.getAllGridColumns().map((col) => col.getColDef()),
      );
      params.api.setGridOption("columnDefs", updatedColumnDefs);
      if (props.onColumnMoved) props.onColumnMoved(params);
    };
    const onColumnResized = (params) => {
      if (!realRef.current?.api) return;

      const gridApi = realRef.current.api;
      const containerElement = document.querySelector(".ag-theme-shadcn");
      if (!containerElement) return;

      const containerWidth = containerElement.clientWidth;

      // Get only visible columns
      const columns = gridApi.getColumns();
      if (!columns) return;

      const totalWidth = columns.reduce(
        (sum, col) => sum + col.getActualWidth(),
        0,
      );

      // If total width is less than container width, reset column sizes
      if (totalWidth < containerWidth) {
        params.api.sizeColumnsToFit();
      }
    };
    if (props.rowData.length === 0 && displayEmptyAlert) {
      return (
        <div className="flex h-full w-full items-center justify-center rounded-md border">
          <Alert variant={"default"} className="w-fit">
            <ForwardedIconComponent
              name="AlertCircle"
              className="text-primary h-5 w-5"
            />
            <AlertTitle>{alertTitle}</AlertTitle>
            <AlertDescription>{alertDescription}</AlertDescription>
          </Alert>
        </div>
      );
    }

    if (colDef.length === 0) {
      {
        return (
          <div className="flex h-full w-full items-center justify-center rounded-md border">
            <Alert variant={"default"} className="w-fit">
              <ForwardedIconComponent
                name="AlertCircle"
                className="text-primary h-5 w-5"
              />
              <AlertTitle>{NO_COLUMN_DEFINITION_ALERT_TITLE}</AlertTitle>
              <AlertDescription>
                {NO_COLUMN_DEFINITION_ALERT_DESCRIPTION}
              </AlertDescription>
            </Alert>
          </div>
        );
      }
    }
    return (
      <div
        className={cn(
          dark ? "ag-theme-quartz-dark" : "ag-theme-quartz",
          "ag-theme-shadcn flex h-full flex-col",
          "relative",
        )} // applying the grid theme
      >
        <AgGridReact
          {...props}
          defaultColDef={{
            minWidth: 100,
            suppressColumnsToolPanel: true, // Don't show hidden columns in tool panel
          }}
          animateRows={false}
          gridOptions={{
            colResizeDefault: "shift",
            suppressColumnVirtualisation: false, // Enable column virtualization for better performance
            ...props.gridOptions,
          }}
          onColumnResized={onColumnResized}
          columnDefs={colDef}
          ref={(node) => {
            if (!node) return;
            realRef.current = node;
            if (typeof ref === "function") {
              ref(node);
            } else if (ref) {
              ref.current = node;
            }
          }}
          onGridReady={onGridReady}
          onColumnMoved={onColumnMoved}
          onStateUpdated={(e) => {
            if (e.sources.some((source) => source.includes("column"))) {
              localStorage.setItem(
                storeReference,
                JSON.stringify(realRef.current?.api?.getColumnState()),
              );
              setColumnStateChange(true);
            }
          }}
        />
        {!props.tableOptions?.hide_options && props.pagination && (
          <TableOptions
            tableOptions={props.tableOptions}
            stateChange={columnStateChange}
            paginationInfo={props.paginationInfo}
            hasSelection={realRef.current?.api?.getSelectedRows()?.length > 0}
            duplicateRow={props.onDuplicate ? props.onDuplicate : undefined}
            deleteRow={props.onDelete ? props.onDelete : undefined}
            addRow={props.addRow ? props.addRow : undefined}
            resetGrid={() => {
              resetGrid(realRef, initialColumnDefs);
              setTimeout(() => {
                setColumnStateChange(false);
                localStorage.removeItem(storeReference);
              }, 100);
            }}
          />
        )}
      </div>
    );
  },
);

export default TableComponent;
