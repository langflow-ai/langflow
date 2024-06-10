import { ColDef, ColGroupDef } from "ag-grid-community";
import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import TableComponent from "../../components/tableComponent";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
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
  const [activeTab, setActiveTab] = useState("Executions");
  const noticed = useRef(false);

  useEffect(() => {
    if (activeTab === "Executions") {
      getTransactionTable(currentFlowId, "union").then((data) => {
        const { columns, rows } = data;
        setColumns(columns.map((col) => ({ ...col, editable: true })));
        setRows(rows);
      });
    } else if (activeTab === "Messages") {
      getMessagesTable("union", currentFlowId, ["index", "flow_id"]).then(
        (data) => {
          const { columns, rows } = data;
          setColumns(columns.map((col) => ({ ...col, editable: true })));
          setRows(rows);
        },
      );
    }

    if (open && activeTab === "Messages" && !noticed.current) {
      const haStream = nodes
        .map((nodes) => (nodes.data as NodeDataType).node!.template)
        .some((template) => template["stream"] && template["stream"].value);
      console.log(
        haStream,
        nodes.map((nodes) => (nodes.data as NodeDataType).node!.template),
      );
      if (haStream) {
        setNoticeData({
          title: "Streamed messages will not appear in this table.",
        });
        noticed.current = true;
      }
    }
    if (!open) {
      noticed.current = false;
    }
  }, [open, activeTab]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="large">
      <BaseModal.Header description="Inspect component executions and monitor sent messages in the playground.">
        <div className="flex w-full justify-between">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Logs</span>
            <IconComponent name="ScrollText" className="mr-2 h-4 w-4 " />
          </div>
          <div className="flex h-fit w-32 items-center"></div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className={
            "text-center; inset-0 m-0 mb-2 flex flex-col self-center overflow-hidden rounded-md border bg-muted pb-1"
          }
        >
          <TabsList>
            <TabsTrigger value={"Executions"}>Executions</TabsTrigger>
            <TabsTrigger value={"Messages"}>Messages</TabsTrigger>
          </TabsList>
        </Tabs>
        <TableComponent
          key={activeTab}
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
