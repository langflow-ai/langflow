import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact, AgGridReactProps } from "ag-grid-react";
import { ElementRef, forwardRef, useEffect, useRef } from "react";
import {
  DEFAULT_TABLE_ALERT_MSG,
  DEFAULT_TABLE_ALERT_TITLE,
} from "../../constants/constants";
import { useDarkStore } from "../../stores/darkStore";
import "../../style/ag-theme-shadcn.css"; // Custom CSS applied to the grid
import { cn, toTitleCase } from "../../utils/utils";
import ForwardedIconComponent from "../genericIconComponent";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { Toggle } from "../ui/toggle";
import ShadTooltip from "../shadTooltipComponent";
import resetGrid from "./utils/reset-grid-columns";
import ResetColumns from "./components/ResetColumns";

interface TableComponentProps extends AgGridReactProps {
  columnDefs: NonNullable<AgGridReactProps["columnDefs"]>;
  rowData: NonNullable<AgGridReactProps["rowData"]>;
  alertTitle?: string;
  alertDescription?: string;
  editable?: boolean | string[];
}

const TableComponent = forwardRef<
  ElementRef<typeof AgGridReact>,
  TableComponentProps
>(
  (
    {
      alertTitle = DEFAULT_TABLE_ALERT_TITLE,
      alertDescription = DEFAULT_TABLE_ALERT_MSG,
      ...props
    },
    ref,
  ) => {
    let colDef = props.columnDefs.map((col, index) => {
      let newCol = {
        ...col,
        headerName: toTitleCase(col.headerName),
      };
      if (index === props.columnDefs.length - 1) {
        newCol = {
          ...newCol,
          resizable: false,
        };
      }
      if (props.onSelectionChanged && index === 0) {
        newCol = {
          ...newCol,
          checkboxSelection: true,
          headerCheckboxSelection: true,
          headerCheckboxSelectionFilteredOnly: true,
        };
      }
      if (
        (typeof props.editable === "boolean" && props.editable) ||
        (Array.isArray(props.editable) &&
          props.editable.includes(newCol.headerName ?? ""))
      ) {
        newCol = {
          ...newCol,
          editable: true,
        };
      }
      return newCol;
    });
    const gridRef = useRef(null);
    // @ts-ignore
    const realRef = ref?.current ? ref : gridRef;
    const dark = useDarkStore((state) => state.dark);
    const initialColumnDefs = useRef(colDef);

    const makeLastColumnNonResizable = (columnDefs) => {
      columnDefs.forEach((colDef, index) => {
        colDef.resizable = index !== columnDefs.length - 1;
      });
      return columnDefs;
    };

    const onGridReady = (params) => {
      // @ts-ignore
      realRef.current = params;
      const updatedColumnDefs = makeLastColumnNonResizable([...colDef]);
      params.api.setColumnDefs(updatedColumnDefs);
      initialColumnDefs.current = params.api.getColumnDefs();
      if (props.onGridReady) props.onGridReady(params);
    };

    const onColumnMoved = (params) => {
      const updatedColumnDefs = makeLastColumnNonResizable(
        params.columnApi.getAllGridColumns().map((col) => col.getColDef()),
      );
      params.api.setColumnDefs(updatedColumnDefs);
      if (props.onColumnMoved) props.onColumnMoved(params);
    };

    if (props.rowData.length === 0) {
      return (
        <div className="flex h-full w-full items-center justify-center rounded-md border">
          <Alert variant={"default"} className="w-fit">
            <ForwardedIconComponent
              name="AlertCircle"
              className="h-5 w-5 text-primary"
            />
            <AlertTitle>{alertTitle}</AlertTitle>
            <AlertDescription>{alertDescription}</AlertDescription>
          </Alert>
        </div>
      );
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
          className={cn(props.className, "custom-scroll")}
          defaultColDef={{
            minWidth: 100,
          }}
          columnDefs={colDef}
          ref={realRef}
          getRowId={(params) => {
            return params.data.id;
          }}
          pagination={true}
          onGridReady={onGridReady}
          onColumnMoved={onColumnMoved}
        />
        <ResetColumns resetGrid={() => resetGrid(realRef, initialColumnDefs)} />
      </div>
    );
  },
);

export default TableComponent;
