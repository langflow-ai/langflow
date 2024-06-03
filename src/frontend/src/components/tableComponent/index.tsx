import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact, AgGridReactProps } from "ag-grid-react";
import { ElementRef, forwardRef, useRef } from "react";
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
    document.querySelector(".ag-paging-page-size")!.style.display = "none";
    const gridRef = useRef(null);
    const realRef = ref?.current ? ref : gridRef;
    const dark = useDarkStore((state) => state.dark);

    const makeLastColumnNonResizable = (columnDefs) => {
      columnDefs.forEach((colDef, index) => {
        colDef.resizable = index !== columnDefs.length - 1;
      });
      return columnDefs;
    };

    const onGridReady = (params) => {
      realRef.current = params;
      const updatedColumnDefs = makeLastColumnNonResizable([
        ...props.columnDefs,
      ]);
      params.api.setColumnDefs(updatedColumnDefs);
      if (props.onGridReady) props.onGridReady(params);
    };

    const onColumnMoved = (params) => {
      const updatedColumnDefs = makeLastColumnNonResizable(
        params.columnApi.getAllGridColumns().map((col) => col.getColDef()),
      );
      params.api.setColumnDefs(updatedColumnDefs);
      if (props.onColumnMoved) props.onColumnMoved(params);
    };

    let colDef = props.columnDefs.map((col, index) => {
      let newCol = {
        ...col,
        headerName: toTitleCase(col.headerName),
      };
      if (index === props.columnDefs.length - 1) {
        newCol = {
          ...col,
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
    let rowDef = props.rowData;

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
          rowData={rowDef}
          ref={realRef}
          pagination={true}
          onGridReady={onGridReady}
          onColumnMoved={onColumnMoved}
        />
        {/*<div className="absolute left-2 bottom-1 cursor-pointer">
          <div
            className="flex h-10 items-center justify-center px-2 pl-3 rounded-md border border-ring/60 text-sm text-[#bccadc] ring-offset-background placeholder:text-muted-foreground hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => setShow(!show)}
          >
            <ForwardedIconComponent name="Settings"></ForwardedIconComponent>
            <ForwardedIconComponent name={show ? "ChevronLeft" : "ChevronRight"} className="transition-all"></ForwardedIconComponent>
          </div>
        </div>*/}
        <div
          className={cn(
            "absolute bottom-1 left-2 rounded-md border border-border transition-all",
          )}
        >
          <ShadTooltip content={"Reset Columns"} styleClasses="z-50">
            <Toggle
              className="h-10 w-10"
              onClick={() => {
                resetGrid(realRef);
              }}
            >
              <ForwardedIconComponent
                name="RotateCcw"
                strokeWidth={2}
                className="h-8 w-8 text-[#bccadc]"
              ></ForwardedIconComponent>
            </Toggle>
          </ShadTooltip>
        </div>
      </div>
    );
  },
);

export default TableComponent;
