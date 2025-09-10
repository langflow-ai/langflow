import IconComponent from "@/components/common/genericIconComponent";
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

      if (data?.rows?.length > 0) {
        // Sort rows by timestamp (latest first) BEFORE converting to display format
        const sortedRows = [...data.rows].sort((a: any, b: any) => {
          const timestampA = new Date(a.timestamp).getTime();
          const timestampB = new Date(b.timestamp).getTime();
          return timestampB - timestampA;
        });

        // Now convert timestamps to display format
        const processedRows = sortedRows.map((row: any) => ({
          ...row,
          timestamp: convertUTCToLocalTimezone(row.timestamp)
        }));

        setRows(processedRows);
      } else {
        setRows(rows);
      }

      setColumns(columns.map((col) => ({ ...col, editable: true })));
    }
  }, [data]);

  // Refetch data when pagination parameters change
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
        <TableComponent
          key={"Executions"}
          readOnlyEdit
          className="h-max-full h-full w-full"
          pagination={false}
          columnDefs={columns}
          autoSizeStrategy={{ type: "fitGridWidth" }}
          rowData={rows}
          headerHeight={rows.length === 0 ? 0 : undefined}
        ></TableComponent>
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
