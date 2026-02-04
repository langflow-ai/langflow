import type { ColDef } from "ag-grid-community";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

export const createDatasetColumns = (): ColDef[] => {
  const baseCellClass =
    "text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none";

  return [
    {
      headerName: "Name",
      field: "name",
      flex: 2,
      sortable: false,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: false,
      filter: "agTextColumnFilter",
      cellClass: baseCellClass,
      cellRenderer: (params: any) => (
        <div className="flex items-center gap-3 font-medium">
          <ForwardedIconComponent
            name="Database"
            className="h-4 w-4 text-muted-foreground"
          />
          <div className="flex flex-col">
            <div className="text-sm font-medium">{params.value}</div>
          </div>
        </div>
      ),
    },
    {
      headerName: "Description",
      field: "description",
      flex: 2,
      sortable: false,
      filter: "agTextColumnFilter",
      editable: false,
      cellClass: baseCellClass,
      valueGetter: (params: any) => params.data.description || "-",
    },
    {
      headerName: "Items",
      field: "item_count",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: "Created",
      field: "created_at",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params: any) => formatDate(params.value),
    },
    {
      headerName: "Updated",
      field: "updated_at",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params: any) => formatDate(params.value),
    },
  ];
};
