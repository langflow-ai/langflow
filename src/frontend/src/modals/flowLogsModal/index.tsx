import { ColDef, ColGroupDef } from "ag-grid-community";
import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import TableComponent from "../../components/tableComponent";
import { getMessagesTable, getTransactionTable } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { NodeDataType } from "../../types/flow";
import BaseModal from "../baseModal";

export default function FlowLogsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const nodes = useFlowStore((state) => state.nodes);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  const [columns, setColumns] = useState<Array<ColDef | ColGroupDef>>([]);
  const [rows, setRows] = useState<any>([]);
  const noticed = useRef(false);

  useEffect(() => {
    getTransactionTable(currentFlowId, "union").then((data) => {
      const { columns, rows } = data;
      setColumns(columns.map((col) => ({ ...col, editable: true })));
      setRows(rows);
    });
  }, [open]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="large">
      <BaseModal.Header description="Inspect component executions.">
        <div className="flex w-full justify-between">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Logs</span>
            <IconComponent name="ScrollText" className="mr-2 h-4 w-4 " />
          </div>
          <div className="flex h-fit w-32 items-center"></div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <TableComponent
          key={"Executions"}
          readOnlyEdit
          className="h-max-full h-full w-full"
          pagination={rows.length === 0 ? false : true}
          columnDefs={columns}
          autoSizeStrategy={{ type: "fitGridWidth" }}
          rowData={rows}
          headerHeight={rows.length === 0 ? 0 : undefined}
        ></TableComponent>
      </BaseModal.Content>
    </BaseModal>
  );
}
