import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { ComponentPropsWithoutRef, ElementRef, forwardRef } from "react";
import { useDarkStore } from "../../stores/darkStore";
import "../../style/ag-theme-shadcn.css"; // Custom CSS applied to the grid
import { cn } from "../../utils/utils";
import { Card, CardContent } from "../ui/card";

const TableComponent = forwardRef<
  ElementRef<typeof AgGridReact>,
  ComponentPropsWithoutRef<typeof AgGridReact>
>(({ pagination = true, ...props }, ref) => {
  const dark = useDarkStore((state) => state.dark);

  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          dark ? "ag-theme-quartz-dark" : "ag-theme-quartz",
          "ag-theme-shadcn flex h-full flex-col",
        )} // applying the grid theme
      >
        <Card x-chunk="dashboard-04-chunk-2" className="pt-4">
          <CardContent>
            <AgGridReact
              overlayNoRowsTemplate="No data available"
              ref={ref}
              {...props}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
});

export default TableComponent;
