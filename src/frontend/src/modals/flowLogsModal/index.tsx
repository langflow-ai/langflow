import IconComponent from "@/components/common/genericIconComponent";
import LoadingComponent from "@/components/common/loadingComponent";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { convertUTCToLocalTimezone } from "@/utils/utils";
import type { ColDef, ColGroupDef } from "ag-grid-community";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import BaseModal from "../baseModal";

export default function FlowLogsModal({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [open, setOpen] = useState(false);

  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [columns, setColumns] = useState<Array<ColDef | ColGroupDef>>([]);
  const [rows, setRows] = useState<any>([]);
  const [searchParams] = useSearchParams();
  const flowIdFromUrl = searchParams.get("id");

  const { data, isLoading, refetch } = useGetTransactionsQuery({
    id: currentFlowId ?? flowIdFromUrl,
    params: {
      page: pageIndex,
      size: pageSize,
    },
    mode: "union",
  });

  useEffect(() => {
    if (data) {
      const { columns, rows } = data;

      // Convert timestamps to local timezone format (backend handles sorting)
      const processedRows =
        rows?.length > 0
          ? rows.map((row: any) => ({
              ...row,
              timestamp: convertUTCToLocalTimezone(row.timestamp),
            }))
          : rows;

      setRows(processedRows);
      
      // Customize column configurations
      const customizedColumns = columns.map((col) => {
        // Check if it's a ColDef (not ColGroupDef) before accessing properties
        if ('field' in col) {
          const columnField = col.field;
          const customCol = { ...col, editable: false };

          if (columnField && ['id'].includes(columnField)) {
            customCol.minWidth = 320;
            customCol.filter = false;
            customCol.sortable = false;

         
          }
          
          // Hide filters for specific columns
          if (columnField && ['vertex_id', 'target_id', 'status'].includes(columnField)) {
            customCol.filter = false;
            customCol.sortable = false;
            customCol.flex = 1;
          }
          
          // Set same width for inputs and outputs columns
          if (columnField && ['inputs', 'outputs'].includes(columnField)) {
            customCol.flex = 1.5;
          }
          
          return customCol;
        }
        
        // Return ColGroupDef as is (no editable property for groups)
        return col;
      });
      
      setColumns(customizedColumns);
    }
  }, [data]);

  useEffect(() => {
    if (open) {
      refetch();
    }
  }, [pageIndex, pageSize, open, refetch]);

  const handlePageChange = useCallback((newPageIndex, newPageSize) => {
    setPageIndex(newPageIndex);
    setPageSize(newPageSize);
  }, []);

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-large">
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header description="Inspect component executions.">
        <div className="flex w-full justify-between">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Logs</span>
            <IconComponent name="ScrollText" className="mr-2 h-4 w-4" />
          </div>
          <div className="flex h-fit w-32 items-center"></div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="relative h-full w-full">
          <TableComponent
            key={"Executions"}
            className="h-max-full h-full w-full"
            pagination={false}
            columnDefs={columns}
            autoSizeStrategy={{ type: "fitGridWidth" }}
            rowData={rows}
            headerHeight={rows.length === 0 ? 0 : undefined}
            gridOptions={{
              suppressCellFocus: true,
              suppressRowClickSelection: true,
              suppressColumnVirtualisation: true,
              suppressRowDeselection: true,
            }}
          ></TableComponent>

          {/* Loading overlay */}
          {isLoading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
              <LoadingComponent remSize={8} />
            </div>
          )}
        </div>

        {!isLoading && (data?.pagination.pages ?? 0) > 1 && (
          <div className="flex justify-end px-3 py-4">
            <PaginatorComponent
              pageIndex={pageIndex}
              pageSize={pageSize}
              rowsCount={[12, 24, 48, 96]}
              totalRowsCount={data?.pagination.total ?? 0}
              paginate={handlePageChange}
              pages={data?.pagination.pages}
            />
          </div>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}
