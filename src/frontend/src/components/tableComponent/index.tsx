import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact, AgGridReactProps } from "ag-grid-react";
import { ElementRef, forwardRef, useCallback } from "react";
import {
  DEFAULT_TABLE_ALERT_MSG,
  DEFAULT_TABLE_ALERT_TITLE,
} from "../../constants/constants";
import { useDarkStore } from "../../stores/darkStore";
import "../../style/ag-theme-shadcn.css"; // Custom CSS applied to the grid
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../genericIconComponent";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";

interface TableComponentProps extends AgGridReactProps {
  columnDefs: NonNullable<AgGridReactProps["columnDefs"]>;
  rowData: NonNullable<AgGridReactProps["rowData"]>;
  alertTitle?: string;
  alertDescription?: string;
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
    ref
  ) => {
    const dark = useDarkStore((state) => state.dark);
    var currentRowHeight: number;
    var minRowHeight = 25;

    const getRowHeight = useCallback(() => {
      return currentRowHeight;
    }, []);

    const onGridReady = useCallback((params: any) => {
      minRowHeight = params.api.getSizesForCurrentTheme().rowHeight;
      currentRowHeight = minRowHeight;
    }, []);

    const updateRowHeight = (params: { api: any }) => {
      const bodyViewport = document.querySelector(".ag-body-viewport");
      if (!bodyViewport) {
        return;
      }
      var gridHeight = bodyViewport.clientHeight;
      var renderedRowCount = params.api.getDisplayedRowCount();

      if (renderedRowCount * minRowHeight >= gridHeight) {
        if (currentRowHeight !== minRowHeight) {
          currentRowHeight = minRowHeight;
          params.api.resetRowHeights();
        }
      } else {
        currentRowHeight = Math.floor(gridHeight / renderedRowCount);
        params.api.resetRowHeights();
      }
    };

    const onFirstDataRendered = useCallback(
      (params: any) => {
        updateRowHeight(params);
      },
      [updateRowHeight]
    );

    const onGridSizeChanged = useCallback(
      (params: any) => {
        updateRowHeight(params);
      },
      [updateRowHeight]
    );

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
          "ag-theme-shadcn flex h-full flex-col"
        )} // applying the grid theme
      >
        <AgGridReact
          {...props}
          className={cn(props.className, "custom-scroll")}
          getRowHeight={getRowHeight}
          onGridReady={onGridReady}
          onFirstDataRendered={onFirstDataRendered}
          onGridSizeChanged={onGridSizeChanged}
          defaultColDef={{
            minWidth: 100,
          }}
          ref={ref}
        />
      </div>
    );
  }
);

export default TableComponent;
