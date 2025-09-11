import IconComponent from "@/components/common/genericIconComponent";
import LoadingComponent from "@/components/common/loadingComponent";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import BaseModal from "../baseModal";
import { createFlowLogsColumns } from "./config/flowLogsColumns";

export default function FlowLogsModal({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [open, setOpen] = useState(false);

  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(24);
  const [rows, setRows] = useState<any>([]);
  const [searchParams] = useSearchParams();
  const flowIdFromUrl = searchParams.get("id");
  
  const columnDefs = createFlowLogsColumns();

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
      const { rows } = data;
      // Set rows directly - timestamp conversion is now handled in column config
      setRows(rows || []);
    }
  }, [data]);

  useEffect(() => {
    if (open) {
      refetch();
    }
  }, [pageIndex, pageSize, open, refetch]);

  const handlePageChange = useCallback((newPageIndex: number, newPageSize: number) => {
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
        <div className="flex h-full flex-col">
          <div className="relative h-full">
            <TableComponent
              key="FlowExecutions"
              rowHeight={45}
              headerHeight={45}
              cellSelection={false}
              tableOptions={{
                hide_options: true,
              }}
              columnDefs={columnDefs}
              rowData={rows}
              className={cn(
                "ag-no-border ag-flow-logs-table w-full h-full"
              )}
              pagination={false}
              autoSizeStrategy={{ type: "fitGridWidth" }}
              gridOptions={{
                suppressCellFocus: true,
                suppressRowClickSelection: true,
                suppressColumnVirtualisation: true,
                suppressRowDeselection: true,
                stopEditingWhenCellsLoseFocus: true,
                ensureDomOrder: true,
                colResizeDefault: "shift",
              }}
            />

            {/* Loading overlay */}
            {isLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                <LoadingComponent remSize={8} />
              </div>
            )}
          </div>

          {/* External Pagination */}
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
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
