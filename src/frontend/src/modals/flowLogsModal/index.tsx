import type { CellClickedEvent } from "ag-grid-community";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { TransactionLogsRow } from "@/types/api";
import { convertUTCToLocalTimezone } from "@/utils/utils";
import BaseModal from "../baseModal";
import { LogDetailViewer } from "./components/LogDetailViewer";
import { createFlowLogsColumns } from "./config/flowLogsColumns";

interface DetailViewState {
  open: boolean;
  title: string;
  content: Record<string, unknown> | null;
}

export default function FlowLogsModal({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [open, setOpen] = useState(false);

  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [rows, setRows] = useState<TransactionLogsRow[]>([]);
  const [searchParams] = useSearchParams();
  const [detailView, setDetailView] = useState<DetailViewState>({
    open: false,
    title: "",
    content: null,
  });
  const columns = createFlowLogsColumns();
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
      const { rows } = data;

      if (rows?.length > 0) {
        rows.forEach((row) => {
          row.timestamp = convertUTCToLocalTimezone(row.timestamp);
        });
      }

      setRows(rows);
    }
  }, [data]);

  useEffect(() => {
    if (open) {
      refetch();
    }
  }, [open]);

  const handlePageChange = useCallback(
    (newPageIndex: number, newPageSize: number) => {
      setPageIndex(newPageIndex);
      setPageSize(newPageSize);
    },
    [],
  );

  const handleCellClicked = useCallback((event: CellClickedEvent) => {
    const field = event.colDef.field;
    if (field === "inputs" || field === "outputs") {
      const rowData = event.data as TransactionLogsRow;
      const content = field === "inputs" ? rowData.inputs : rowData.outputs;
      const title = `${rowData.vertex_id} - ${field === "inputs" ? "Inputs" : "Outputs"}`;

      setDetailView({
        open: true,
        title,
        content: content as Record<string, unknown> | null,
      });
    }
  }, []);

  return (
    <>
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
            onCellClicked={handleCellClicked}
          ></TableComponent>
          {!isLoading && (data?.pagination.total ?? 0) >= 10 && (
            <div className="flex justify-end px-3 py-4">
              <PaginatorComponent
                pageIndex={data?.pagination.page ?? 1}
                pageSize={data?.pagination.size ?? 10}
                rowsCount={[12, 24, 48, 96]}
                totalRowsCount={data?.pagination.total ?? 0}
                paginate={handlePageChange}
                pages={data?.pagination.pages}
              />
            </div>
          )}
        </BaseModal.Content>
      </BaseModal>

      <LogDetailViewer
        open={detailView.open}
        onOpenChange={(open) => setDetailView((prev) => ({ ...prev, open }))}
        title={detailView.title}
        content={detailView.content}
      />
    </>
  );
}
