import { ColDef, ColGroupDef } from "ag-grid-community";
import { AxiosError } from "axios";
import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import TableComponent from "../../components/tableComponent";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { getMessagesTable, getTransactionTable } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType, NodeDataType } from "../../types/flow";
import BaseModal from "../baseModal";

export default function FlowLogsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const saveFlow = useFlowsManagerStore((state) => state.saveFlow);
  const nodes = useFlowStore((state) => state.nodes);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  useEffect(() => {
    setName(currentFlow!.name);
    setDescription(currentFlow!.description);
  }, [currentFlow!.name, currentFlow!.description, open]);

  const [name, setName] = useState(currentFlow!.name);
  const [description, setDescription] = useState(currentFlow!.description);
  const [columns, setColumns] = useState<Array<ColDef | ColGroupDef>>([]);
  const [rows, setRows] = useState<any>([]);
  const [activeTab, setActiveTab] = useState("Executions");
  const noticed = useRef(false);

  function handleClick(): void {
    currentFlow!.name = name;
    currentFlow!.description = description;
    saveFlow(currentFlow!)
      ?.then(() => {
        setOpen(false);
      })
      .catch((err) => {
        useAlertStore.getState().setErrorData({
          title: "Error while saving changes",
          list: [(err as AxiosError).response?.data.detail ?? ""],
        });
        console.error(err);
      });
  }

  useEffect(() => {
    if (activeTab === "Executions") {
      getTransactionTable(currentFlowId, "union").then((data) => {
        const { columns, rows } = data;
        setColumns(columns.map((col) => ({ ...col, editable: true })));
        setRows(rows);
      });
    } else if (activeTab === "Messages") {
      getMessagesTable(currentFlowId, "union").then((data) => {
        const { columns, rows } = data;
        setColumns(columns.map((col) => ({ ...col, editable: true })));
        setRows(rows);
      });
    }

    if (open && activeTab === "Messages" && !noticed.current) {
      const haStream = nodes
        .map((nodes) => (nodes.data as NodeDataType).node!.template)
        .some((template) => template["stream"] && template["stream"].value);
      console.log(
        haStream,
        nodes.map((nodes) => (nodes.data as NodeDataType).node!.template)
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

  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    const tempNameList: string[] = [];
    flows.forEach((flow: FlowType) => {
      if ((flow.is_component ?? false) === false) tempNameList.push(flow.name);
    });
    setNameList(tempNameList.filter((name) => name !== currentFlow!.name));
  }, [flows]);

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
