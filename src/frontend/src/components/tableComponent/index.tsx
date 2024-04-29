import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { ComponentPropsWithoutRef, ElementRef, forwardRef } from "react";
import { useDarkStore } from "../../stores/darkStore";
import "../../style/ag-theme-shadcn.css"; // Custom CSS applied to the grid
import { cn } from "../../utils/utils";

const TableComponent = forwardRef<
  ElementRef<typeof AgGridReact>,
  ComponentPropsWithoutRef<typeof AgGridReact>
>(({ ...props }, ref) => {
  const dark = useDarkStore((state) => state.dark);

  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          dark ? "ag-theme-quartz-dark" : "ag-theme-quartz",
          "ag-theme-shadcn flex h-full flex-col pb-8"
        )} // applying the grid theme
      >
        <AgGridReact ref={ref} pagination={true} {...props} />
      </div>
    </div>
  );
});

export default TableComponent;
