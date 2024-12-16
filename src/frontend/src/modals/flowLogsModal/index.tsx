import IconComponent from "@/components/common/genericIconComponent";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowSettingsPropsType } from "@/types/components";
import { ColDef, ColGroupDef } from "ag-grid-community";
import { useCallback, useEffect, useState } from "react";
import BaseModal from "../baseModal";

export default function FlowLogsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [columns, setColumns] = useState<Array<ColDef | ColGroupDef>>([]);
  const [rows, setRows] = useState<any>([]);

  const { data, isLoading, refetch } = useGetTransactionsQuery({
    id: currentFlowId,
    params: {
      page: pageIndex,
      size: pageSize,
    },
    mode: "union",
  });

  useEffect(() => {
    if (data) {
      const { columns, rows } = data;
      setColumns(columns.map((col) => ({ ...col, editable: true })));
      setRows(rows);
    }
  }, [data]);

  useEffect(() => {
    if (open) {
      refetch();
    }
  }, [open]);

  const handlePageChange = useCallback((newPageIndex, newPageSize) => {
    setPageIndex(newPageIndex);
    setPageSize(newPageSize);
  }, []);

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-large">
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
  );
}
