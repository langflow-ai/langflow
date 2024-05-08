import { useEffect, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/tabs";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType } from "../../types/flow";
import BaseModal from "../baseModal";
import TableComponent from "../../components/tableComponent";

export default function FlowLogsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const saveFlow = useFlowsManagerStore((state) => state.saveFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flows = useFlowsManagerStore((state) => state.flows);
  useEffect(() => {
    setName(currentFlow!.name);
    setDescription(currentFlow!.description);
  }, [currentFlow!.name, currentFlow!.description, open]);

  const [name, setName] = useState(currentFlow!.name);
  const [description, setDescription] = useState(currentFlow!.description);

  function handleClick(): void {
    currentFlow!.name = name;
    currentFlow!.description = description;
    saveFlow(currentFlow!);
    setOpen(false);
  }

  const [nameLists, setNameList] = useState<string[]>([]);

  const [activeTab, setActiveTab] = useState("logs");

  useEffect(() => {
    const tempNameList: string[] = [];
    flows.forEach((flow: FlowType) => {
      if ((flow.is_component ?? false) === false) tempNameList.push(flow.name);
    });
    setNameList(tempNameList.filter((name) => name !== currentFlow!.name));
  }, [flows]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="large-h-full">
      <BaseModal.Header description={null}>
        <div className="flex w-full justify-between">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Logs</span>
            <IconComponent name="Settings2" className="mr-2 h-4 w-4 " />
          </div>
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className={"api-modal-tabs inset-0 m-0 self-center"}
          >
            <TabsList>
              <TabsTrigger value={"logs"}>Logs View</TabsTrigger>
              <TabsTrigger value={"session"}>Session View</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="flex h-fit w-32 items-center"></div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <TableComponent columnDefs={[]} rowData={[]}></TableComponent>
      </BaseModal.Content>
    </BaseModal>
  );
}
