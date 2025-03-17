import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import EditFlowSettings from "../../components/core/editFlowSettingsComponent";
import SchedulerComponent from "../../components/schedulerComponent";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants/constants";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType } from "../../types/flow";
import { isEndpointNameValid } from "../../utils/utils";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
  flowData,
  details,
}: FlowSettingsPropsType): JSX.Element {
  const saveFlow = useSaveFlow();
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const flows = useFlowsManagerStore((state) => state.flows);
  const flow = flowData ?? currentFlow;
  const [activeTab, setActiveTab] = useState("details");

  useEffect(() => {
    setName(flow?.name ?? "");
    setDescription(flow?.description ?? "");
  }, [flow?.name, flow?.description, open]);

  const [name, setName] = useState(flow?.name ?? "");
  const [description, setDescription] = useState(flow?.description ?? "");
  const [endpoint_name, setEndpointName] = useState(flow?.endpoint_name ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [disableSave, setDisableSave] = useState(true);
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  function handleClick(): void {
    setIsSaving(true);
    if (!flow) return;
    const newFlow = cloneDeep(flow);
    newFlow.name = name;
    newFlow.description = description;
    newFlow.endpoint_name =
      endpoint_name && endpoint_name.length > 0 ? endpoint_name : null;
    if (autoSaving) {
      saveFlow(newFlow)
        ?.then(() => {
          setOpen(false);
          setIsSaving(false);
          setSuccessData({ title: "Changes saved successfully" });
        })
        .catch(() => {
          setIsSaving(false);
        });
    } else {
      setCurrentFlow(newFlow);
      setOpen(false);
      setIsSaving(false);
    }
  }

  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    if (flows) {
      const tempNameList: string[] = [];
      flows.forEach((flow: FlowType) => {
        tempNameList.push(flow.name);
      });
      setNameList(tempNameList.filter((name) => name !== flow!.name));
    }
  }, [flows]);

  useEffect(() => {
    if (
      (!nameLists.includes(name) && flow?.name !== name) ||
      flow?.description !== description ||
      ((flow?.endpoint_name ?? "") !== endpoint_name &&
        isEndpointNameValid(endpoint_name ?? "", 50))
    ) {
      setDisableSave(false);
    } else {
      setDisableSave(true);
    }
  }, [nameLists, flow, description, endpoint_name, name]);

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="smaller-h-full"
      onSubmit={handleClick}
    >
      <BaseModal.Header description={SETTINGS_DIALOG_SUBTITLE}>
        <span className="pr-2">Flow Settings</span>
        <IconComponent name="Settings" className="mr-2 h-4 w-4" />
      </BaseModal.Header>
      <BaseModal.Content>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="scheduler">Scheduler</TabsTrigger>
          </TabsList>
          <TabsContent value="details" className="mt-4">
            <EditFlowSettings
              invalidNameList={nameLists}
              name={name}
              description={description}
              endpointName={endpoint_name}
              setName={setName}
              setDescription={setDescription}
              setEndpointName={details ? undefined : setEndpointName}
            />
          </TabsContent>
          <TabsContent value="scheduler" className="mt-4">
            {flow?.id && <SchedulerComponent flowId={flow.id} />}
          </TabsContent>
        </Tabs>
      </BaseModal.Content>

      <BaseModal.Footer
        submit={{
          label: "Save",
          dataTestId: "save-flow-settings",
          disabled: activeTab === "details" ? disableSave : false,
          loading: isSaving,
        }}
      />
    </BaseModal>
  );
}
